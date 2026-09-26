import json

import pytest
from asg_stagecraft import StoryGenerator
from asg_stagecraft import pipeline as pipeline_module
from asg_stagecraft.formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from asg_stagecraft.runtime.errors import GeminiDailyQuotaError
from asg_stagecraft.stage.schemas import NarrationArtifact, PerformanceArtifact
from stage_fakes import StageFakeProvider
from test_generator_v5 import major_story_review, make_request


def generate(tmp_path, provider=None, **kwargs):
    generator = StoryGenerator(
        provider or StageFakeProvider(story_review=major_story_review()),
        tmp_path,
        story_format=StoryFormat.SIMULATED,
        **kwargs,
    )
    events = []
    return generator.generate(make_request(), on_event=events.append), events


def read_json(run, name):
    return json.loads((run.run_dir / name).read_text(encoding="utf-8"))


def test_simulated_run_writes_every_artifact_and_completes(tmp_path) -> None:
    run, _ = generate(tmp_path)
    metadata = read_json(run, "metadata.json")
    assert metadata["status"] == "completed"
    assert metadata["story_format"] == "simulated"
    assert metadata["script_method"] == "native"
    assert metadata["narrative_voice"] == "omniscient"
    assert metadata["actor_memory"] == "own"
    for name in (
        "story_plan.json",
        "script.json",
        "script.md",
        "cast_bible.json",
        "performance.json",
        "performance.md",
        "narration.json",
        "simulation_metrics.json",
        "story_metrics.json",
        "story.md",
    ):
        assert (run.run_dir / name).is_file(), name
    assert run.performance_path.is_file()
    assert run.narration_path.is_file()
    completed = metadata["completed_stages"]
    assert completed == sorted(completed, key=pipeline_module.CHECKPOINT_STAGES.index)
    for stage in ("casting", "performance", "narration", "story"):
        assert stage in completed


def test_the_story_is_prose_narrated_from_the_log_not_the_script(tmp_path) -> None:
    run, _ = generate(tmp_path)
    story = run.story_path.read_text(encoding="utf-8")
    script = (run.run_dir / "script.md").read_text(encoding="utf-8")
    assert story != script
    # The rendered script uses the printed-play convention; the narrated story never does.
    assert ".—" in script
    assert ".—" not in story
    assert story.startswith("# ")
    assert "## " in story


def test_the_plan_and_cast_are_untouched_by_the_simulation(tmp_path) -> None:
    narrative = StoryGenerator(
        StageFakeProvider(story_review=major_story_review()), tmp_path
    ).generate(make_request())
    simulated, _ = generate(tmp_path)
    for name in ("story_plan.json", "characters.json", "world.json"):
        assert (simulated.run_dir / name).read_text(encoding="utf-8") == (
            narrative.run_dir / name
        ).read_text(encoding="utf-8"), name


def test_no_actor_ever_sees_the_plan_or_a_future_scene(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review())
    run, _ = generate(tmp_path, provider)
    plan = read_json(run, "story_plan.json")
    forbidden = {event["id"] for event in plan["events"]}
    forbidden |= {event["title"] for event in plan["events"]}
    forbidden |= {chapter["id"] for chapter in plan["chapters"]}
    for context in provider.actor_contexts:
        for token in forbidden:
            assert token not in context, token
    # The director's own book is allowed to hold them; the actors' contexts are not.
    assert provider.actor_contexts


def test_a_character_only_remembers_what_it_witnessed(tmp_path) -> None:
    run, _ = generate(tmp_path)
    performance = PerformanceArtifact.model_validate(read_json(run, "performance.json"))
    turns = {turn.id: turn for scene in performance.scenes for turn in scene.turns}
    assert turns
    for character_id in (
        member["character_id"] for member in read_json(run, "script.json")["cast"]
    ):
        records = read_json(run, f"memory/{character_id}/records.json")
        for record in records:
            if not record["turn_id"]:
                continue
            assert character_id in turns[record["turn_id"]].witnesses
            if record["kind"] == "thought":
                assert turns[record["turn_id"]].actor_id == character_id


def test_shared_memory_widens_the_witness_set(tmp_path) -> None:
    own, _ = generate(tmp_path, actor_memory=ActorMemory.OWN)
    shared, _ = generate(tmp_path, actor_memory=ActorMemory.SHARED)
    own_performance = PerformanceArtifact.model_validate(read_json(own, "performance.json"))
    shared_performance = PerformanceArtifact.model_validate(read_json(shared, "performance.json"))
    assert own_performance.settings.actor_memory is ActorMemory.OWN
    assert shared_performance.settings.actor_memory is ActorMemory.SHARED
    own_witnesses = sum(
        len(turn.witnesses) for scene in own_performance.scenes for turn in scene.turns
    )
    shared_witnesses = sum(
        len(turn.witnesses) for scene in shared_performance.scenes for turn in scene.turns
    )
    assert shared_witnesses >= own_witnesses


@pytest.mark.parametrize(
    "voice",
    [NarrativeVoice.OMNISCIENT, NarrativeVoice.FOCALIZED, NarrativeVoice.FIRST_PERSON],
)
def test_every_voice_produces_a_story_and_records_itself(tmp_path, voice) -> None:
    run, _ = generate(tmp_path, narrative_voice=voice)
    narration = NarrationArtifact.model_validate(read_json(run, "narration.json"))
    assert narration.narrative_voice is voice
    assert run.story_path.read_text(encoding="utf-8").strip()
    if voice is NarrativeVoice.FIRST_PERSON:
        assert narration.narrator_character_id
        for chapter in narration.chapters:
            assert chapter.turns_visible <= chapter.turns_available
    else:
        assert not narration.narrator_character_id


def test_the_voice_only_changes_the_narration(tmp_path) -> None:
    omniscient, _ = generate(tmp_path, narrative_voice=NarrativeVoice.OMNISCIENT)
    focalized, _ = generate(tmp_path, narrative_voice=NarrativeVoice.FOCALIZED)
    for name in ("story_plan.json", "script.json"):
        assert (omniscient.run_dir / name).read_text(encoding="utf-8") == (
            focalized.run_dir / name
        ).read_text(encoding="utf-8"), name


def test_two_identical_runs_produce_identical_logs(tmp_path) -> None:
    first, _ = generate(tmp_path)
    second, _ = generate(tmp_path)
    for name in ("performance.json", "cast_bible.json", "simulation_metrics.json"):
        assert read_json(first, name) == read_json(second, name), name


def test_casting_degrades_to_a_derived_bible(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), fail_casting_call={1, 2})
    run, _ = generate(tmp_path, provider)
    metadata = read_json(run, "metadata.json")
    assert any("CASTING_FALLBACK" in warning for warning in metadata["warnings"])
    assert read_json(run, "cast_bible.json")["fallback"] is True
    assert run.story_path.is_file()


def test_a_rejected_turn_is_repaired_and_recorded(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), empty_turn_once=True)
    run, _ = generate(tmp_path, provider)
    performance = PerformanceArtifact.model_validate(read_json(run, "performance.json"))
    assert sum(scene.rejected for scene in performance.scenes) >= 1
    rejected = list(run.run_dir.glob("stage/*/rejected.jsonl"))
    assert rejected
    entries = [
        json.loads(line)
        for path in rejected
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert any(entry["code"] == "EMPTY_TURN" for entry in entries)


def test_a_repeated_line_is_rejected(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), repeat_turn_once=True)
    run, _ = generate(tmp_path, provider)
    entries = [
        json.loads(line)
        for path in run.run_dir.glob("stage/*/rejected.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert any(entry["code"] == "REPEATED_LINE" for entry in entries)


def test_a_beat_that_never_lands_is_forced_and_warned(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), beat_never_achieved=True)
    run, _ = generate(tmp_path, provider, turns_per_beat=2)
    metadata = read_json(run, "metadata.json")
    assert any("BEAT_FORCED" in warning for warning in metadata["warnings"])
    metrics = read_json(run, "simulation_metrics.json")
    assert metrics["beats_forced"] >= 1
    assert metrics["beat_completion_ratio"] < 1.0


def test_a_beat_the_world_resolves_is_counted_as_reached_with_help(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), beat_needs_world=True)
    run, _ = generate(tmp_path, provider, turns_per_beat=2)
    metrics = read_json(run, "simulation_metrics.json")
    assert metrics["beats_intervened"] >= 1
    assert metrics["beats_forced"] == 0
    assert metrics["reaction_turns"] == 2 * metrics["beats_intervened"]
    assert metrics["stage_events"] >= metrics["beats_intervened"]
    assert "final" in provider.check_modes


def test_every_director_call_lands_in_director_jsonl(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), beat_never_achieved=True)
    run, _ = generate(tmp_path, provider, turns_per_beat=2)
    entries = [
        json.loads(line)
        for path in sorted(run.run_dir.glob("stage/*/director.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    calls = [
        name
        for name, _, _ in provider.structured_calls
        if name in {"BeatDirection", "BeatCheckDraft"}
    ]
    assert len(entries) == len(calls)
    assert {entry["mode"] for entry in entries} == {"open", "stall", "final"}
    assert all(entry["achieved"] is False for entry in entries if entry["mode"] == "final")


def test_the_last_scene_of_the_play_ends_in_a_coda(tmp_path) -> None:
    run, _ = generate(tmp_path)
    performance = PerformanceArtifact.model_validate(read_json(run, "performance.json"))
    assert performance.contract_version == "2"
    assert performance.scenes[-1].coda_turns > 0
    assert all(scene.coda_turns == 0 for scene in performance.scenes[:-1])
    assert read_json(run, "simulation_metrics.json")["coda_turns"] == (
        performance.scenes[-1].coda_turns
    )


def test_the_narrator_is_told_which_moments_the_chapter_turns_on(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review())
    generate(tmp_path, provider)
    assert any("[clave]" in prompt for prompt in provider.narrator_prompts)


def test_the_new_measurements_are_recorded(tmp_path) -> None:
    run, _ = generate(tmp_path)
    metrics = read_json(run, "simulation_metrics.json")
    for key in (
        "action_repetition_ratio",
        "first_person_actions",
        "thought_ratio",
        "long_speeches",
        "yields",
        "max_tactic_streak",
        "compression_ratio",
        "log_words",
    ):
        assert key in metrics, key
    assert metrics["gates_known_by_discoverer"] == 0
    assert metrics["log_words"] > 0


def test_the_narrator_falls_back_without_losing_the_run(tmp_path) -> None:
    provider = StageFakeProvider(
        story_review=major_story_review(), fail_narrator_call={1, 2, 3, 4, 5, 6}
    )
    run, _ = generate(tmp_path, provider)
    metadata = read_json(run, "metadata.json")
    assert any("NARRATION_FALLBACK" in warning for warning in metadata["warnings"])
    story = run.story_path.read_text(encoding="utf-8")
    assert "—" in story
    assert read_json(run, "simulation_metrics.json")["narration_source_fallbacks"] >= 1


def test_the_director_failing_does_not_stop_the_performance(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), fail_director=True)
    run, _ = generate(tmp_path, provider, turns_per_beat=2)
    assert run.story_path.is_file()
    metadata = read_json(run, "metadata.json")
    assert any("BEAT_CHECK_FALLBACK" in warning for warning in metadata["warnings"])


@pytest.mark.parametrize("role", ["casting", "actor", "director", "narrator"])
def test_quota_errors_abort_a_simulated_run(tmp_path, role) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), quota_error_at_stage=role)
    with pytest.raises(GeminiDailyQuotaError):
        generate(tmp_path, provider)


def test_no_measurement_ever_reaches_a_stage_prompt(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review())
    generate(tmp_path, provider)
    prompts = [prompt for _, prompt in provider.text_calls] + [
        prompt for _, _, prompt in provider.structured_calls
    ]
    for needle in (
        "beat_completion_ratio",
        "script_echo",
        "repetition_ratio",
        "dialogue_ratio",
        "compression_ratio",
        "action_repetition_ratio",
        "max_tactic_streak",
        "thought_ratio",
        "importance:",
        "word budget",
    ):
        assert not any(needle in prompt for prompt in prompts), needle


def test_the_run_records_what_each_agent_was_told(tmp_path) -> None:
    run, _ = generate(tmp_path)
    actors = list(run.run_dir.glob("stage/actors/*.json"))
    assert actors
    for path in actors:
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["system_instruction"].strip()
        assert document["dossier"]["character_id"] == document["character_id"]
    contexts = list(run.run_dir.glob("stage/*/contexts.jsonl"))
    assert contexts
    entries = [
        json.loads(line)
        for path in contexts
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert all(entry["context"].strip() for entry in entries)


def test_progress_is_non_decreasing_and_reaches_completion(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review())
    generator = StoryGenerator(provider, tmp_path, story_format=StoryFormat.SIMULATED)
    updates = []
    generator.generate(make_request(), on_progress=updates.append)
    percents = [update.percent for update in updates]
    assert percents == sorted(percents)
    assert percents[-1] == 100


def test_script_runs_are_unaffected_by_the_simulation_stages(tmp_path) -> None:
    run = StoryGenerator(
        StageFakeProvider(story_review=major_story_review()),
        tmp_path,
        story_format=StoryFormat.SCRIPT,
        script_method=ScriptMethod.NATIVE,
    ).generate(make_request())
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["narrative_voice"] is None
    assert metadata["actor_memory"] is None
    for name in ("cast_bible.json", "performance.json", "narration.json", "script.md"):
        assert not (run.run_dir / name).exists(), name
    for stage in ("casting", "performance", "narration"):
        assert stage not in metadata["completed_stages"]
