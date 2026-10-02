import json
import uuid
from datetime import UTC, datetime

import pytest
from asg_stagecraft import StoryGenerator
from asg_stagecraft import pipeline as pipeline_module
from asg_stagecraft.formats import (
    ActorMemory,
    NarrativeVoice,
    ScriptMethod,
    SimulationMode,
    StoryFormat,
    voice_choice,
)
from asg_stagecraft.runtime.errors import GeminiDailyQuotaError
from asg_stagecraft.runtime.provider import RoutedProvider, current_call_context
from asg_stagecraft.schemas import LLMUsageRecord
from asg_stagecraft.stage.schemas import NarrationArtifact, PerformanceArtifact
from asg_stagecraft.tools import recompute
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
    assert read_json(run, "promise_audit.json")["source"] == "performance"
    assert (run.run_dir / "script_promise_audit.json").is_file()
    assert (run.run_dir / "stage/promise_audit_draft.json").is_file()
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


@pytest.mark.parametrize("voice", list(NarrativeVoice))
def test_every_voice_produces_a_story_and_records_itself(tmp_path, voice) -> None:
    run, _ = generate(tmp_path, narrative_voice=voice)
    narration = NarrationArtifact.model_validate(read_json(run, "narration.json"))
    assert narration.narrative_voice is voice
    assert narration.contract_version == "2"
    assert run.story_path.read_text(encoding="utf-8").strip()
    if voice_choice(voice).takes_character:
        assert narration.narrator_character_id
        for chapter in narration.chapters:
            assert chapter.turns_visible <= chapter.turns_available
    else:
        assert not narration.narrator_character_id
        assert narration.narrator_source == "none"


def upstream_calls(provider):
    """Every model call made before the narrator's first one, in order."""
    structured = [(name, system, prompt) for name, system, prompt in provider.structured_calls]
    text = [
        (system, prompt)
        for system, prompt in provider.text_calls
        if "You are the Narrator" not in system
    ]
    return structured, text


def test_the_voice_only_changes_the_narration(tmp_path) -> None:
    """Voice, narrator and tone must leave every artifact and prompt before narration alike."""
    first = StageFakeProvider(story_review=major_story_review())
    second = StageFakeProvider(story_review=major_story_review())
    omniscient, _ = generate(tmp_path, first, narrative_voice=NarrativeVoice.OMNISCIENT)
    limited, _ = generate(
        tmp_path,
        second,
        narrative_voice=NarrativeVoice.LIMITED,
        narrator="Ana",
        narration_tone="como un guerrero samurai, con tono medieval",
    )
    for name in ("story_plan.json", "script.json", "cast_bible.json", "performance.json"):
        assert (omniscient.run_dir / name).read_text(encoding="utf-8") == (
            limited.run_dir / name
        ).read_text(encoding="utf-8"), name
    assert upstream_calls(first) == upstream_calls(second)
    narrator_systems = [system for system, _ in second.text_calls if "Narrator" in system]
    assert narrator_systems
    assert all("The point-of-view character is Ana." in item for item in narrator_systems)
    assert all("guerrero samurai" in item for item in narrator_systems)
    assert not any("guerrero" in system for system, _ in first.text_calls)


def test_the_chosen_character_is_recorded_as_requested(tmp_path) -> None:
    run, _ = generate(tmp_path, narrative_voice=NarrativeVoice.FIRST_PERSON, narrator="ana")
    narration = NarrationArtifact.model_validate(read_json(run, "narration.json"))
    assert narration.requested_narrator == "ana"
    assert narration.narrator_character_id == "ana"
    assert narration.narrator_source == "requested"
    assert read_json(run, "metadata.json")["warnings"] == []


def test_an_unknown_narrator_falls_back_and_warns(tmp_path) -> None:
    run, events = generate(tmp_path, narrative_voice=NarrativeVoice.LIMITED, narrator="Zoe")
    narration = NarrationArtifact.model_validate(read_json(run, "narration.json"))
    assert narration.narrator_character_id == "ana"
    assert narration.narrator_source == "most_turns"
    warnings = read_json(run, "metadata.json")["warnings"]
    assert any(item.startswith("[NARRATOR_FALLBACK]") and "Zoe" in item for item in warnings)
    assert any(event.kind == "narrator_fallback" for event in events)


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
    assert performance.contract_version == "4"
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


def test_a_narrator_failure_leaves_its_exception_on_disk(tmp_path) -> None:
    """Found in 7.1: a failed narration was swallowed without saying why, unlike the Writer."""
    provider = StageFakeProvider(story_review=major_story_review(), fail_narrator_call={1})
    run, _ = generate(tmp_path, provider)
    error = read_json(run, "narration/chapter-001-attempt-001-error.json")
    assert error["exception_type"] == "RuntimeError"
    assert (run.run_dir / "narration" / "chapter-001.md").is_file()


def test_the_turn_log_holds_every_turn_the_performance_counted(tmp_path) -> None:
    """Found in 7.1: turns.jsonl skipped the world's turns, one line short per event."""
    provider = StageFakeProvider(story_review=major_story_review(), beat_needs_world=True)
    run, _ = generate(tmp_path, provider, turns_per_beat=2)
    logged = [
        json.loads(line)
        for path in sorted(run.run_dir.glob("stage/*/turns.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    contexts = [
        line
        for path in sorted(run.run_dir.glob("stage/*/contexts.jsonl"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    metrics = read_json(run, "simulation_metrics.json")
    assert len(logged) == metrics["turns"]
    assert any(item["kind"] == "world" for item in logged)
    assert len(contexts) == sum(1 for item in logged if item["kind"] == "actor")


def test_the_measurements_can_be_recomputed_from_the_logs_alone(tmp_path) -> None:
    """The 7.0 runs lacked every figure 7.1 added, and the doc quoted them recomputed by hand."""
    run, _ = generate(tmp_path)
    original = (run.run_dir / "simulation_metrics.json").read_bytes()
    assert recompute.main([str(run.run_dir)]) == 0
    assert read_json(run, recompute.OUTPUT_NAME) == read_json(run, "simulation_metrics.json")
    assert (run.run_dir / "simulation_metrics.json").read_bytes() == original


def test_every_stage_call_is_tagged_with_its_agent(tmp_path) -> None:
    """MED-2: the stage field repeated the schema, so actor, director and narrator were guesses."""
    contexts: list[tuple[str, str]] = []

    class TaggingProvider(StageFakeProvider):
        def generate_structured(self, **kwargs):
            contexts.append(current_call_context())
            return super().generate_structured(**kwargs)

        def generate_text(self, **kwargs):
            contexts.append(current_call_context())
            return super().generate_text(**kwargs)

    generate(tmp_path, TaggingProvider(story_review=major_story_review()))
    assert all(stage and agent for stage, agent in contexts), contexts
    assert {("performance", "actor"), ("performance", "stage_manager")} <= set(contexts)
    assert ("narration", "narrator") in set(contexts)


class RecordingStageProvider(StageFakeProvider):
    """Record every call the way GeminiProvider does, under this double's own model name."""

    def __init__(self, model_name: str, **kwargs) -> None:
        super().__init__(story_review=major_story_review(), **kwargs)
        self.model_name = model_name

    def _record_call(self) -> None:
        stage, agent = current_call_context()
        record = LLMUsageRecord(
            call_id=uuid.uuid4().hex,
            operation="fake",
            stage=stage or "fake",
            agent=agent,
            attempt=1,
            status="succeeded",
            model=self.model_name,
            timestamp=datetime.now(UTC),
        )
        self.usage_records.append(record)
        if self.usage_callback:
            self.usage_callback(record)

    def generate_structured(self, **kwargs):
        self._record_call()
        return super().generate_structured(**kwargs)

    def generate_text(self, **kwargs):
        self._record_call()
        return super().generate_text(**kwargs)


PERFORMANCE_SCHEMAS = {"ActorTurnDraft", "BeatDirection", "BeatCheckDraft", "ReflectionDraft"}


def test_the_performance_can_run_on_a_model_of_its_own(tmp_path) -> None:
    """7.4: the actors spend most of a run's calls, so they may draw on another model's quota."""
    main = RecordingStageProvider("main-model")
    stage = RecordingStageProvider("stage-model")
    run, _ = generate(tmp_path, RoutedProvider(main, stage))
    main_schemas = {name for name, *_ in main.structured_calls}
    stage_schemas = {name for name, *_ in stage.structured_calls}
    assert stage_schemas and stage_schemas <= PERFORMANCE_SCHEMAS
    assert not main_schemas & PERFORMANCE_SCHEMAS
    # Casting and narration stay on the main model: the narration is the text that is evaluated.
    assert "CastBibleDraft" in main_schemas
    assert main.narrator_prompts and not stage.text_calls
    metadata = read_json(run, "metadata.json")
    assert metadata["status"] == "completed"
    assert (metadata["model"], metadata["stage_model"]) == ("main-model", "stage-model")
    lines = (run.run_dir / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()
    calls = [json.loads(line) for line in lines]
    assert {item["model"] for item in calls if item["stage"] == "performance"} == {"stage-model"}
    assert {item["model"] for item in calls if item["stage"] != "performance"} == {"main-model"}
    assert read_json(run, "llm_usage.json")["calls"] == len(calls)


def test_a_run_without_a_performance_names_no_performance_model(tmp_path) -> None:
    routed = RoutedProvider(RecordingStageProvider("main-model"), RecordingStageProvider("other"))
    run = StoryGenerator(routed, tmp_path).generate(make_request())
    metadata = read_json(run, "metadata.json")
    assert (metadata["model"], metadata["stage_model"]) == ("main-model", None)
    assert routed.stage.structured_calls == []


def test_each_actor_records_how_it_left_every_scene(tmp_path) -> None:
    """emotions was always []: nothing filled it, although every reflection names one."""
    run, _ = generate(tmp_path)
    actors = read_json(run, "simulation_metrics.json")["actor_metrics"]
    assert actors and all(item["emotions"] for item in actors)
    assert {emotion for item in actors for emotion in item["emotions"]} == {"inquieta"}


def test_the_director_failing_does_not_stop_the_performance(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), fail_director=True)
    run, _ = generate(tmp_path, provider, turns_per_beat=2)
    assert run.story_path.is_file()
    metadata = read_json(run, "metadata.json")
    assert any("BEAT_CHECK_FALLBACK" in warning for warning in metadata["warnings"])


def test_a_failure_in_the_performance_names_its_scene(tmp_path) -> None:
    """MED-4: 054422 died in the performance and its report said only "provider"."""
    provider = StageFakeProvider(story_review=major_story_review(), quota_error_at_stage="actor")
    with pytest.raises(GeminiDailyQuotaError):
        generate(tmp_path, provider)
    run_dir = next(iter(tmp_path.iterdir()))
    report = json.loads((run_dir / "error_report.json").read_text(encoding="utf-8"))
    assert report["stage"] == "performance"
    assert report["details"]["component"] == "provider"
    assert report["details"]["scene_id"].endswith("scene-1")


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


def test_adaptive_run_can_end_open_when_actors_refuse_a_beat(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), beat_never_achieved=True)
    run, _ = generate(tmp_path, provider, simulation_mode=SimulationMode.ADAPTIVE, turns_per_beat=2)
    performance = read_json(run, "performance.json")
    assert performance["settings"]["simulation_mode"] == "adaptive"
    assert len(performance["scenes"]) == 1
    assert not performance["scenes"][0]["beats"][0]["achieved"]
    assert not performance["scenes"][0]["beats"][0]["forced"]
    assert list(run.run_dir.glob("active_plan/revision-*.json"))
    revision_logs = list(run.run_dir.glob("active_plan/revision-*-attempts.jsonl"))
    assert revision_logs
    statuses = [
        json.loads(line)["status"]
        for line in revision_logs[0].read_text(encoding="utf-8").splitlines()
    ]
    assert statuses == ["requested", "proposed", "accepted"]
    assert not list(run.run_dir.glob("stage/*/checkpoint.json")) == []
    assert read_json(run, "story_metrics.json")["events"] == 0


def test_a_new_performance_reuses_the_exact_plan_script_and_cast(tmp_path) -> None:
    """Paired modes can share the same initial causes and actor dossiers."""
    original, _ = generate(tmp_path, audio=False)
    replay = StoryGenerator(
        StageFakeProvider(story_review=major_story_review()),
        tmp_path,
        story_format=StoryFormat.SIMULATED,
        simulation_mode=SimulationMode.ADAPTIVE,
        audio=False,
    ).generate_from_plan(original.run_dir)
    assert read_json(replay, "metadata.json")["status"] == "completed"
    assert read_json(replay, "source_run.json")["run_id"] == original.run_dir.name
    for name in (
        "request.json",
        "world.json",
        "characters.json",
        "story_plan.json",
        "script.json",
        "cast_bible.json",
    ):
        assert (replay.run_dir / name).read_bytes() == (original.run_dir / name).read_bytes()
    assert read_json(replay, "performance.json")["settings"]["simulation_mode"] == "adaptive"


def test_the_inventory_dresses_the_stage_and_arbitrates_the_performance(tmp_path) -> None:
    """7.6: the objects of the world were ignored, so a seal changed hands with no hand-over."""
    provider = StageFakeProvider(story_review=major_story_review())
    run, _ = generate(tmp_path, provider, inventory=True)
    metadata = read_json(run, "metadata.json")
    assert metadata["status"] == "completed"
    completed = metadata["completed_stages"]
    assert completed == sorted(completed, key=pipeline_module.CHECKPOINT_STAGES.index)
    assert completed.index("casting") < completed.index("props") < completed.index("performance")
    assert read_json(run, "generation_options.json")["inventory"] is True

    props = read_json(run, "props.json")
    assert [item["name"] for item in props["props"]] == [
        "Una llave de laton",
        "Un cuaderno cosido",
        "Un farol apagado",
    ]
    assert props["fallback"] is False

    performance = PerformanceArtifact.model_validate(read_json(run, "performance.json"))
    assert performance.contract_version == "4"
    assert performance.settings.inventory is True
    assert [item.id for item in performance.props] == ["prop-1", "prop-2", "prop-3"]
    moves = [
        turn.item_action
        for scene in performance.scenes
        for turn in scene.turns
        if turn.item_action is not None
    ]
    assert moves, "the actors never handled an object"
    # Every move the log kept is one the arbiter accepted, with the object resolved to an id.
    assert all(item.item_id and item.item_name and item.witnesses for item in moves)
    assert {item.verb for item in moves} <= {"use", "give", "take", "drop", "hide", "show"}

    logged = (run.run_dir / "stage/inventory.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(logged) == len(moves)
    cast = {turn.actor_id for scene in performance.scenes for turn in scene.turns}
    # Every line says who ended up holding the object: a cast member, or nobody.
    assert all(json.loads(line)["holder_id"] in {"", *cast} for line in logged)

    metrics = read_json(run, "simulation_metrics.json")
    assert metrics["inventory"] is True
    assert metrics["props"] == 3
    assert metrics["item_actions"] == len(moves)
    assert metrics["props_used_ratio"] > 0
    assert metrics["item_witness_share"] > 0
    # Measured from the log alone, so a finished run can be measured again without quota.
    assert recompute.main([str(run.run_dir)]) == 0
    assert read_json(run, recompute.OUTPUT_NAME) == metrics

    # The actors were told what they carry, and still never what the plan holds.
    assert any("LO QUE LLEVAS:" in context for context in provider.actor_contexts)
    plan = read_json(run, "story_plan.json")
    forbidden = {event["id"] for event in plan["events"]}
    forbidden |= {item.id for item in performance.props}
    for context in provider.actor_contexts:
        for token in forbidden:
            assert token not in context, token
    # And no figure of the stage reached the prop master either.
    props_prompts = [
        prompt for name, _, prompt in provider.structured_calls if name == "PropListDraft"
    ]
    assert len(props_prompts) == 1
    for needle in ("MAX_PERSONAL_PROPS", "at most 2", "props_used_ratio"):
        assert needle not in props_prompts[0], needle


def test_without_the_inventory_no_object_reaches_a_prompt_or_an_artifact(tmp_path) -> None:
    """The control arm: a run with the option off is the run 7.5 produced, prompt for prompt."""
    provider = StageFakeProvider(story_review=major_story_review())
    run, _ = generate(tmp_path, provider)
    assert not (run.run_dir / "props.json").exists()
    assert not (run.run_dir / "stage/inventory.jsonl").exists()
    assert "props" not in read_json(run, "metadata.json")["completed_stages"]
    performance = PerformanceArtifact.model_validate(read_json(run, "performance.json"))
    assert performance.settings.inventory is False
    assert performance.props == [] and performance.inventory == []
    assert all(turn.item_action is None for scene in performance.scenes for turn in scene.turns)
    # The actor schema is the one every earlier run used, and no object block was ever rendered.
    schemas = {name for name, *_ in provider.structured_calls}
    assert "ActorTurnDraft" in schemas
    assert "ActorTurnWithItemsDraft" not in schemas and "PropListDraft" not in schemas
    prompts = [prompt for _, prompt in provider.text_calls] + [
        prompt for _, _, prompt in provider.structured_calls
    ]
    for needle in ("LO QUE LLEVAS", "LO QUE VES", "UTILERIA", "WHAT YOU ARE CARRYING"):
        assert not any(needle in prompt for prompt in prompts), needle
    systems = {system for system, _, _ in provider.structured_calls}
    assert not any("WHAT YOU ARE CARRYING" in system for system in systems)


def test_the_stage_is_dressed_from_the_world_when_the_prop_master_fails(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review(), fail_props_call={1, 2})
    run, events = generate(tmp_path, provider, inventory=True)
    assert run.story_path.is_file()
    assert read_json(run, "props.json")["fallback"] is True
    warnings = read_json(run, "metadata.json")["warnings"]
    assert any("PROPS_FALLBACK" in warning for warning in warnings)
    assert any(event.kind == "props_fallback" for event in events)
