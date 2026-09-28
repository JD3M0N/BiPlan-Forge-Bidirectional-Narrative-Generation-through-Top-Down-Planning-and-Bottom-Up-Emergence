"""7.3: every run records its options, and a caller can stop a run between two agent calls."""

import json

import pytest
from asg_stagecraft import GenerationOptions, StoryGenerator
from asg_stagecraft.formats import NarrativeVoice, StoryFormat
from asg_stagecraft.runtime.errors import NON_DEGRADABLE_ERRORS, RunCancelledError
from asg_stagecraft.schemas import StoryRequest
from stage_fakes import StageFakeProvider
from test_generator_v5 import FakeProvider, major_story_review, make_request


def read_json(run_dir, name):
    return json.loads((run_dir / name).read_text(encoding="utf-8"))


def only_run(root):
    (run_dir,) = [path for path in root.iterdir() if path.is_dir()]
    return run_dir


class AgentCounter:
    """Count agent calls from the event stream and ask to stop after a given number."""

    def __init__(self, stop_after: int | None = None, stop_at_stage: str | None = None) -> None:
        self.stop_after = stop_after
        self.stop_at_stage = stop_at_stage
        self.agents = 0
        self.stage = ""
        self.asked = 0

    def on_event(self, event) -> None:
        if event.kind == "agent_called":
            self.agents += 1

    def on_progress(self, update) -> None:
        if update.stage != "rate_limit":
            self.stage = update.stage

    def should_cancel(self) -> bool:
        self.asked += 1
        if self.stop_at_stage is not None:
            return self.stage == self.stop_at_stage
        return self.stop_after is not None and self.agents >= self.stop_after


def test_every_run_records_its_options_in_the_manifest(tmp_path) -> None:
    options = GenerationOptions(promise_ledger=False, narrative_guidance=False, audio=False)
    run = StoryGenerator.from_options(FakeProvider(), tmp_path, options).generate(make_request())
    assert run.options_path.is_file()
    assert GenerationOptions.model_validate(read_json(run.run_dir, "generation_options.json")) == (
        options
    )
    manifest = read_json(run.run_dir, "pipeline_manifest.json")
    assert "generation_options.json" in manifest["artifacts"]
    assert not run.brief_path.exists()


def test_a_simulated_run_records_the_voice_it_was_asked_for(tmp_path) -> None:
    generator = StoryGenerator(
        StageFakeProvider(story_review=major_story_review()),
        tmp_path,
        story_format=StoryFormat.SIMULATED,
        narrative_voice=NarrativeVoice.FIRST_PERSON,
    )
    run = generator.generate(make_request())
    recorded = read_json(run.run_dir, "generation_options.json")
    assert recorded["story_format"] == "simulated"
    assert recorded["narrative_voice"] == "first_person"


def test_a_run_whose_analysis_failed_still_records_its_options(tmp_path) -> None:
    class BrokenAnalyst(FakeProvider):
        def generate_structured(self, *, system_instruction, prompt, schema, profile):
            if schema is StoryRequest:
                raise ValueError("the analyst could not read the request")
            return super().generate_structured(
                system_instruction=system_instruction, prompt=prompt, schema=schema, profile=profile
            )

    with pytest.raises(ValueError):
        StoryGenerator(BrokenAnalyst(), tmp_path, audio=False).generate("Una historia")
    run_dir = only_run(tmp_path)
    assert read_json(run_dir, "generation_options.json")["audio"] is False


def test_a_cancel_stops_the_run_before_the_next_agent_call(tmp_path) -> None:
    provider = FakeProvider()
    counter = AgentCounter(stop_after=3)
    with pytest.raises(RunCancelledError):
        StoryGenerator(provider, tmp_path).generate(
            make_request(),
            on_event=counter.on_event,
            on_progress=counter.on_progress,
            should_cancel=counter.should_cancel,
        )
    assert counter.agents == 3
    run_dir = only_run(tmp_path)
    metadata = read_json(run_dir, "metadata.json")
    assert metadata["status"] == "failed"
    assert metadata["error_code"] == "RUN_CANCELLED"
    report = read_json(run_dir, "error_report.json")
    assert report["code"] == "RUN_CANCELLED"
    assert report["stage"] == metadata["error_stage"]
    assert "cancel" in report["summary"]


def test_a_degradable_stage_does_not_swallow_a_cancel(tmp_path) -> None:
    """The architect degrades on any other failure; a cancel must still end the run."""
    counter = AgentCounter(stop_at_stage="architecture")
    with pytest.raises(RunCancelledError):
        StoryGenerator(FakeProvider(), tmp_path).generate(
            make_request(),
            on_event=counter.on_event,
            on_progress=counter.on_progress,
            should_cancel=counter.should_cancel,
        )
    metadata = read_json(only_run(tmp_path), "metadata.json")
    assert metadata["error_code"] == "RUN_CANCELLED"
    assert metadata["error_stage"] == "architecture"
    assert "architecture" not in metadata["completed_stages"]
    assert not any("ARCHITECT" in warning for warning in metadata["warnings"])


def test_a_cancel_stops_a_performance_mid_scene(tmp_path) -> None:
    provider = StageFakeProvider(story_review=major_story_review())
    counter = AgentCounter(stop_at_stage="performance")
    with pytest.raises(RunCancelledError):
        StoryGenerator(provider, tmp_path, story_format=StoryFormat.SIMULATED).generate(
            make_request(),
            on_event=counter.on_event,
            on_progress=counter.on_progress,
            should_cancel=counter.should_cancel,
        )
    run_dir = only_run(tmp_path)
    assert read_json(run_dir, "metadata.json")["error_stage"] == "performance"
    assert not (run_dir / "performance.json").exists()


def test_a_cancel_that_arrives_while_the_story_is_published_is_ignored(tmp_path) -> None:
    counter = AgentCounter(stop_at_stage="story")
    run = StoryGenerator(FakeProvider(), tmp_path).generate(
        make_request(),
        on_event=counter.on_event,
        on_progress=counter.on_progress,
        should_cancel=counter.should_cancel,
    )
    assert read_json(run.run_dir, "metadata.json")["status"] == "completed"


def test_a_run_nobody_cancels_asks_before_every_agent_call(tmp_path) -> None:
    counter = AgentCounter()
    StoryGenerator(FakeProvider(), tmp_path).generate(
        make_request(),
        on_event=counter.on_event,
        on_progress=counter.on_progress,
        should_cancel=counter.should_cancel,
    )
    assert counter.asked == counter.agents > 0


def test_a_cancel_is_never_degraded() -> None:
    assert RunCancelledError in NON_DEGRADABLE_ERRORS
