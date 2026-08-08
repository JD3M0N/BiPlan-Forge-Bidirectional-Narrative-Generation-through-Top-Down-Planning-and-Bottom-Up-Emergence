import json
import pytest
from asg_top_down.orchestrator import StoryOrchestrator
from fakes import FakeProvider

EXPECTED_FILES = {"story.md", "request.json", "archetypes.json", "story_plan.json", "world.json", "characters.json", "narrative_graph.json", "narrative_graph.md", "scenes", "draft.md", "review.json", "evaluation.json", "metadata.json"}


def test_pipeline_writes_all_v2_artifacts_in_order(tmp_path) -> None:
    provider = FakeProvider()
    run_dir = StoryOrchestrator(provider, tmp_path).run("Una historia")
    assert {path.name for path in run_dir.iterdir()} == EXPECTED_FILES
    assert len(list((run_dir / "scenes").glob("scene-*.md"))) == 2
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["completed_stages"] == ["analyst", "planner", "world", "characters", "director", "graph", "scenes", "review", "story"]
    assert provider.text_calls["scene"] == 2
    assert provider.text_calls["story"] == 1


def test_run_directories_are_unique(tmp_path) -> None:
    orchestrator = StoryOrchestrator(FakeProvider(), tmp_path)
    assert orchestrator.run("Historia") != orchestrator.run("Historia")


def test_failure_preserves_completed_artifacts_and_metadata(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="fallo simulado"):
        StoryOrchestrator(FakeProvider(fail_on="ReviewArtifact"), tmp_path).run("Historia")
    run_dir = next(tmp_path.iterdir())
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["completed_stages"][-1] == "scenes"
    assert (run_dir / "draft.md").exists()
    assert not (run_dir / "story.md").exists()
