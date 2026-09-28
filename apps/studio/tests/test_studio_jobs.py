import threading

from asg_stagecraft import StoryBrief
from asg_stagecraft.runtime.errors import PlotValidationError
from asg_studio.jobs import JobRequest, JobRunner
from studio_fakes import FakeGenerator


def request(title="Una obra"):
    return JobRequest(mode="brief", brief=StoryBrief(plot="Una trama.", title=title))


def runner_with(generator):
    runner = JobRunner(lambda options: generator)
    runner.start()
    return runner


def test_a_job_runs_to_completion_and_keeps_its_story(tmp_path) -> None:
    generator = FakeGenerator(tmp_path)
    runner = runner_with(generator)
    job = runner.submit(request())
    assert runner.wait(5)
    snapshot = runner.snapshot(job["id"])
    assert snapshot["status"] == "completed"
    assert snapshot["run_id"] == "run-1"
    assert snapshot["collection"] == "Stagecraft"
    assert snapshot["counters"] == {"agents": 1, "turns": 1}
    kinds = [event["kind"] for event in snapshot["events"]]
    # A quota wait is an event, never the job's progress; log appends are counted, not kept.
    assert "rate_limit" in kinds and "artifact_updated" not in kinds
    assert isinstance(generator.requests[0], StoryBrief)
    runner.stop()


def test_events_are_served_after_a_sequence_number(tmp_path) -> None:
    runner = runner_with(FakeGenerator(tmp_path))
    job = runner.submit(request())
    runner.wait(5)
    everything = runner.snapshot(job["id"])["events"]
    later = runner.snapshot(job["id"], since=everything[0]["seq"])["events"]
    assert later == everything[1:]
    runner.stop()


def test_jobs_run_one_after_another_and_a_queued_one_can_be_withdrawn(tmp_path) -> None:
    gate = threading.Event()
    generator = FakeGenerator(tmp_path, gate=gate)
    runner = runner_with(generator)
    first = runner.submit(request("primera"))
    second = runner.submit(request("segunda"))
    withdrawn = runner.cancel(second["id"])
    assert withdrawn["status"] == "cancelled"
    gate.set()
    assert runner.wait(5)
    assert runner.snapshot(first["id"])["status"] == "completed"
    assert len(generator.requests) == 1
    assert [job["title"] for job in runner.jobs()] == ["segunda", "primera"]
    runner.stop()


def test_a_running_job_stops_through_should_cancel(tmp_path) -> None:
    gate = threading.Event()
    runner = runner_with(FakeGenerator(tmp_path, gate=gate))
    job = runner.submit(request())
    for _ in range(100):
        if runner.snapshot(job["id"])["status"] == "running":
            break
        threading.Event().wait(0.02)
    snapshot = runner.cancel(job["id"])
    assert snapshot["cancel_requested"] is True
    gate.set()
    assert runner.wait(5)
    assert runner.snapshot(job["id"])["status"] == "cancelled"
    runner.stop()


def test_failures_become_messages_and_never_stop_the_worker(tmp_path) -> None:
    error = PlotValidationError("No se pudo completar el plan.", recommendations=["Reintenta."])
    runner = runner_with(FakeGenerator(tmp_path, fail=error))
    failed = runner.submit(request())
    runner.wait(5)
    assert runner.snapshot(failed["id"])["error"] == {
        "code": "PLOT_VALIDATION_FAILED",
        "summary": "No se pudo completar el plan.",
        "recommendation": "Reintenta.",
    }
    runner.generator_factory = lambda options: FakeGenerator(tmp_path, fail=KeyError("boom"))
    unexpected = runner.submit(request())
    runner.wait(5)
    assert runner.snapshot(unexpected["id"])["error"]["code"] == "UNEXPECTED_ERROR"
    runner.generator_factory = lambda options: FakeGenerator(tmp_path)
    recovered = runner.submit(request())
    runner.wait(5)
    assert runner.snapshot(recovered["id"])["status"] == "completed"
    runner.stop()


def test_a_request_needs_the_source_its_mode_names() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        JobRequest(mode="brief")
    with pytest.raises(ValidationError):
        JobRequest(mode="prompt", prompt="   ")
    assert JobRequest(mode="prompt", prompt=" Hola ").story_request() == "Hola"
