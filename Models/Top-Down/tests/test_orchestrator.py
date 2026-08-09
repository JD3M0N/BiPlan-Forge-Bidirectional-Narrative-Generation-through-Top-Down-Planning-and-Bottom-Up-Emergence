import json
import pytest

from asg_top_down.orchestrator import StoryOrchestrator
from asg_top_down.progress import ProgressUpdate, format_progress
from fakes import FakeProvider, RESPONSES
from asg_top_down.schemas import DirectedStoryArtifact


EXPECTED = {"story.md", "request.json", "archetypes.json", "story_plan.json", "world.json", "characters.json", "storyline.json", "nekg.json", "node_reviews.json", "replanning_history.json", "narrative_graph.json", "narrative_graph.md", "freytag_plan_review.json", "freytag_story_review.json", "scenes", "draft.md", "review.json", "evaluation.json", "metadata.json"}


def test_pipeline_writes_storyteller_artifacts(tmp_path) -> None:
    provider = FakeProvider()
    run_dir = StoryOrchestrator(provider, tmp_path).run("Una historia")
    assert {x.name for x in run_dir.iterdir()} == EXPECTED
    assert len(list((run_dir / "scenes").glob("chapter-*.md"))) == 5
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert provider.text_calls["scene"] == 5


def test_pipeline_reports_monotonic_progress_by_chapter(tmp_path) -> None:
    updates = []

    StoryOrchestrator(FakeProvider(), tmp_path).run(
        "Una historia", on_progress=updates.append
    )

    assert updates[0].percent == 0
    assert updates[-1] == ProgressUpdate(100, "completed", "Historia terminada")
    assert [item.percent for item in updates] == sorted(
        item.percent for item in updates
    )
    chapters = [item for item in updates if item.chapter is not None]
    assert [item.chapter for item in chapters] == [1, 2, 3, 4, 5]
    assert {item.total_chapters for item in chapters} == {5}


def test_progress_bar_has_percentage_and_description() -> None:
    rendered = format_progress(
        ProgressUpdate(80, "scenes", "Escribiendo capítulo 4 de 5", 4, 5)
    )
    assert rendered == "[████████░░] 80% — Escribiendo capítulo 4 de 5"


def test_failure_preserves_metadata(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="fallo simulado"):
        StoryOrchestrator(FakeProvider(fail_on="ReviewArtifact"), tmp_path).run("Historia")
    metadata = json.loads((next(tmp_path.iterdir()) / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"


class ReplanningProvider(FakeProvider):
    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures
        self.director_calls = 0

    def generate_structured(self, *, system_instruction, prompt, schema):
        if schema is DirectedStoryArtifact:
            self.director_calls += 1
            candidate = RESPONSES[DirectedStoryArtifact].model_copy(deep=True)
            if self.director_calls <= self.failures:
                candidate.candidate_edges = [x for x in candidate.candidate_edges if x.target != "node_3"]
            return candidate
        return super().generate_structured(system_instruction=system_instruction, prompt=prompt, schema=schema)


def test_replans_all_cpns_until_cen_is_reachable(tmp_path) -> None:
    provider = ReplanningProvider(failures=2)
    run_dir = StoryOrchestrator(provider, tmp_path).run("Historia")
    history = json.loads((run_dir / "replanning_history.json").read_text(encoding="utf-8"))
    assert provider.director_calls == 3
    assert {x["attempt"] for x in history["attempts"]} == {1, 2}


def test_fails_after_five_transactional_replans(tmp_path) -> None:
    provider = ReplanningProvider(failures=5)
    with pytest.raises(ValueError, match="five replanning attempts"):
        StoryOrchestrator(provider, tmp_path).run("Historia")
    history = json.loads((next(tmp_path.iterdir()) / "replanning_history.json").read_text(encoding="utf-8"))
    assert {x["attempt"] for x in history["attempts"]} == {1, 2, 3, 4, 5}
