import json

import pytest
from asg_stagecraft import StoryGenerator
from asg_stagecraft import pipeline as pipeline_module
from asg_stagecraft.formats import ScriptMethod, StoryFormat
from asg_stagecraft.runtime.errors import GeminiDailyQuotaError
from asg_stagecraft.schemas import PlayScript
from test_generator_v5 import FakeProvider, major_story_review, make_request


def generate(tmp_path, provider, *, method=ScriptMethod.NATIVE, **kwargs):
    generator = StoryGenerator(
        provider,
        tmp_path,
        story_format=StoryFormat.SCRIPT,
        script_method=method,
        **kwargs,
    )
    events = []
    return generator.generate(make_request(), on_event=events.append), events


def test_native_run_writes_script_artifacts_and_completes(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    run, events = generate(tmp_path, provider, method=ScriptMethod.NATIVE)
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["story_format"] == "script"
    assert metadata["script_method"] == "native"
    assert run.story_format is StoryFormat.SCRIPT
    assert run.script_method is ScriptMethod.NATIVE
    for name in (
        "script_presentation.json",
        "acts/act-001.json",
        "acts/act-002.json",
        "draft.md",
        "review.json",
        "promise_audit.json",
        "revisions/act-001.json",
        "revisions/act-002.json",
        "revision_report.json",
        "script.json",
        "script_metrics.json",
        "story.md",
    ):
        assert (run.run_dir / name).is_file(), name
    absent = ("story_metrics.json", "chapters", "draft_presentation.json", "craft_evidence.json")
    for name in absent:
        assert not (run.run_dir / name).exists(), name
    completed = metadata["completed_stages"]
    assert completed == sorted(completed, key=pipeline_module.CHECKPOINT_STAGES.index)
    assert "adaptation" not in completed
    play = PlayScript.model_validate_json(run.script_path.read_text(encoding="utf-8"))
    assert play.script_method is ScriptMethod.NATIVE
    assert len(play.acts) == 2
    agent_names = [
        event.message.rsplit(" ", 1)[-1] for event in events if event.kind == "agent_called"
    ]
    assert agent_names[-6:] == [
        "playwright",
        "playwright",
        "playwright",
        "script_critic",
        "script_writer",
        "script_writer",
    ]


def test_adapted_run_writes_narrative_then_adapts(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    run, events = generate(tmp_path, provider, method=ScriptMethod.ADAPTED)
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["script_method"] == "adapted"
    for name in (
        "chapters/chapter-001.md",
        "revisions/chapter-001.md",
        "revision_report.json",
        "prose.md",
        "script_presentation.json",
        "adaptation/act-001.json",
        "adaptation/act-002.json",
        "script.json",
        "script_metrics.json",
        "story.md",
    ):
        assert (run.run_dir / name).is_file(), name
    completed = metadata["completed_stages"]
    assert completed.index("revision") < completed.index("adaptation")
    assert completed.index("adaptation") < completed.index("story")
    agent_names = [
        event.message.rsplit(" ", 1)[-1] for event in events if event.kind == "agent_called"
    ]
    assert agent_names[-3:] == ["script_adapter", "script_adapter", "script_adapter"]


def test_story_plan_is_identical_across_narrative_and_script_formats(tmp_path) -> None:
    narrative = StoryGenerator(FakeProvider(story_review=major_story_review()), tmp_path).generate(
        make_request()
    )
    native, _ = generate(tmp_path, FakeProvider(story_review=major_story_review()))
    adapted, _ = generate(
        tmp_path, FakeProvider(story_review=major_story_review()), method=ScriptMethod.ADAPTED
    )
    plan_text = (narrative.run_dir / "story_plan.json").read_text(encoding="utf-8")
    assert (native.run_dir / "story_plan.json").read_text(encoding="utf-8") == plan_text
    assert (adapted.run_dir / "story_plan.json").read_text(encoding="utf-8") == plan_text


def test_adapted_prose_matches_a_narrative_run_byte_for_byte(tmp_path) -> None:
    narrative_provider = FakeProvider(story_review=major_story_review())
    narrative = StoryGenerator(narrative_provider, tmp_path).generate(make_request())
    adapted_provider = FakeProvider(story_review=major_story_review())
    adapted, _ = generate(tmp_path, adapted_provider, method=ScriptMethod.ADAPTED)
    narrative_story = narrative.story_path.read_text(encoding="utf-8")
    adapted_prose = (adapted.run_dir / "prose.md").read_text(encoding="utf-8")
    assert adapted_prose == narrative_story
    prefix = adapted_provider.text_calls[: len(narrative_provider.text_calls)]
    assert narrative_provider.text_calls == prefix


def test_script_method_is_inert_for_narrative_runs(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    generator = StoryGenerator(
        provider, tmp_path, story_format=StoryFormat.NARRATIVE, script_method=ScriptMethod.ADAPTED
    )
    run = generator.generate(make_request())
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["story_format"] == "narrative"
    assert metadata["script_method"] is None
    prompts = [prompt for _, prompt in provider.text_calls] + [
        prompt for _, _, prompt in provider.structured_calls
    ]
    assert not any("ACT ANCHOR INDEX" in prompt for prompt in prompts)
    assert not any("Playwright" in prompt for prompt in prompts)


def test_exhausted_act_attempts_abort_native_drafting(tmp_path) -> None:
    provider = FakeProvider(fail_act_call={1, 2, 3})
    with pytest.raises(Exception) as excinfo:
        generate(tmp_path, provider, method=ScriptMethod.NATIVE)
    assert excinfo.value.code == "SCRIPT_VALIDATION_FAILED"
    assert excinfo.value.stage == "drafting"


def test_exhausted_adaptation_attempts_abort_and_keep_prose(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review(), fail_act_call={1, 2, 3})
    with pytest.raises(Exception) as excinfo:
        generate(tmp_path, provider, method=ScriptMethod.ADAPTED)
    assert excinfo.value.code == "SCRIPT_VALIDATION_FAILED"
    assert excinfo.value.stage == "adaptation"


def test_script_writer_falls_back_to_the_drafted_act(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review(), fail_script_writer_call={1, 2, 3, 4})
    run, _ = generate(tmp_path, provider)
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert any("SCRIPT_REVISION_REJECTED" in warning for warning in metadata["warnings"])
    report = json.loads((run.run_dir / "revision_report.json").read_text(encoding="utf-8"))
    assert any(chapter["final_source"] == "draft" for chapter in report["chapters"])


def test_script_critic_failure_delivers_the_drafted_acts(tmp_path) -> None:
    provider = FakeProvider(fail_script_critic=True)
    run, _ = generate(tmp_path, provider)
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "critique" not in metadata["completed_stages"]
    draft = (run.run_dir / "draft.md").read_text(encoding="utf-8")
    story = run.story_path.read_text(encoding="utf-8")
    assert draft == story


@pytest.mark.parametrize("role", ["playwright", "script_critic", "script_writer"])
def test_quota_errors_abort_native_agents(tmp_path, role) -> None:
    kwargs = {"story_review": major_story_review()} if role != "playwright" else {}
    provider = FakeProvider(quota_error_at=role, **kwargs)
    with pytest.raises(GeminiDailyQuotaError):
        generate(tmp_path, provider)


def test_promise_ledger_reaches_playwright_and_script_critic(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    run, _ = generate(tmp_path, provider)
    assert (run.run_dir / "promise_ledger.json").is_file()
    prompts = [prompt for _, _, prompt in provider.structured_calls]
    assert any("PROMISE OBLIGATIONS" in prompt for prompt in prompts)


def test_no_measurement_ever_reaches_a_script_prompt(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    run, _ = generate(tmp_path, provider)
    prompts = [prompt for _, prompt in provider.text_calls] + [
        prompt for _, _, prompt in provider.structured_calls
    ]
    assert not any("dialogue_word_ratio" in prompt for prompt in prompts)
    assert not any("word budget" in prompt for prompt in prompts)


def test_progress_is_non_decreasing_and_reaches_completion(tmp_path) -> None:
    provider = FakeProvider(story_review=major_story_review())
    generator = StoryGenerator(
        provider, tmp_path, story_format=StoryFormat.SCRIPT, script_method=ScriptMethod.NATIVE
    )
    progress = []
    generator.generate(make_request(), on_progress=progress.append)
    percents = [update.percent for update in progress if update.stage != "rate_limit"]
    assert percents == sorted(percents)
    assert percents[-1] == 100
