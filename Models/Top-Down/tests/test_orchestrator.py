import json

import pytest

from asg_top_down.orchestrator import StoryOrchestrator

from fakes import FakeProvider


EXPECTED_FILES = {
    "story.md",
    "request.json",
    "world.json",
    "characters.json",
    "outline.json",
    "draft.md",
    "review.json",
    "metadata.json",
}


def test_pipeline_writes_all_artifacts_in_order(tmp_path) -> None:
    provider = FakeProvider()
    run_dir = StoryOrchestrator(provider, tmp_path).run("Una historia")

    assert {path.name for path in run_dir.iterdir()} == EXPECTED_FILES
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["model"] == "fake-flash"
    assert metadata["completed_stages"] == [
        "analyst",
        "world",
        "characters",
        "outline",
        "draft",
        "review",
        "story",
    ]
    assert provider.calls == [
        ("structured", "StoryRequest"),
        ("structured", "WorldArtifact"),
        ("structured", "CharactersArtifact"),
        ("structured", "OutlineArtifact"),
        ("text", "draft"),
        ("structured", "ReviewArtifact"),
        ("text", "story"),
    ]
    assert provider.text_calls["story"] == 1


def test_run_directories_are_unique(tmp_path) -> None:
    orchestrator = StoryOrchestrator(FakeProvider(), tmp_path)
    first = orchestrator.run("Una historia")
    second = orchestrator.run("Una historia")
    assert first != second
    assert first.exists() and second.exists()


def test_failure_preserves_completed_artifacts_and_metadata(tmp_path) -> None:
    provider = FakeProvider(fail_on="ReviewArtifact")

    with pytest.raises(RuntimeError, match="fallo simulado"):
        StoryOrchestrator(provider, tmp_path).run("Una historia")

    run_dir = next(tmp_path.iterdir())
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["completed_stages"][-1] == "draft"
    assert (run_dir / "draft.md").exists()
    assert not (run_dir / "story.md").exists()
    assert "fallo simulado" in metadata["error"]

