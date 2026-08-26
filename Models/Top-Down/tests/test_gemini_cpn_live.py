"""Opt-in end-to-end checks against the configured Gemini API."""

from __future__ import annotations

import json
import os

import pytest

from asg_top_down.config import load_settings
from asg_top_down.generator import StoryGenerator
from asg_top_down.narrative_db import NarrativeSchemaRepository
from asg_top_down.provider import GeminiProvider
from asg_top_down.schemas import (
    ChapterAnchorsArtifact, CharactersArtifact, IncrementalStorylineArtifact,
    PlotNodeProposal, StoryOutlineArtifact, StoryRequest, WorldArtifact,
)
from asg_top_down.storyline.dependency import DependencyValidator
from asg_top_down.storyline.graph import NarrativeEntityGraph
from asg_top_down.storyline.planner import IncrementalPlotPlanner


LIVE_GEMINI = os.getenv("RUN_GEMINI_INTEGRATION") == "1"


PROMPTS = [
    StoryRequest(
        original_prompt=(
            "Escribe una historia de ciencia ficcion de 600 palabras sobre una cartografa "
            "que debe cruzar una estacion orbital y recuperar un mapa estelar robado."
        ),
        processed_prompt=(
            "Write a 600-word science-fiction story about a cartographer who must cross an "
            "orbital station and recover a stolen star map."
        ),
        title="La ruta de las estrellas", language="Spanish", genre="science fiction",
        tone="melancholic and hopeful", target_words=600,
        premise="A cartographer crosses a failing station to recover a stolen star map.",
    ),
    StoryRequest(
        original_prompt=(
            "Escribe un misterio de 600 palabras: una archivista sigue pistas entre varias "
            "salas para encontrar una llave y descubrir quien borro un expediente."
        ),
        processed_prompt=(
            "Write a 600-word mystery in which an archivist follows clues across several rooms, "
            "finds a key, and learns who erased a case file."
        ),
        title="El expediente borrado", language="Spanish", genre="mystery",
        tone="tense", target_words=600,
        premise="An archivist follows physical clues to uncover who erased a case file.",
    ),
    StoryRequest(
        original_prompt=(
            "Escribe una fantasia de 600 palabras sobre una aprendiz que transporta una reliquia "
            "entre dos santuarios y aprende por que su mentora le oculto la verdad."
        ),
        processed_prompt=(
            "Write a 600-word fantasy about an apprentice carrying a relic between two shrines "
            "and learning why her mentor hid the truth."
        ),
        title="La reliquia entre santuarios", language="Spanish", genre="fantasy",
        tone="wondrous and intimate", target_words=600,
        premise="An apprentice moves a relic between shrines and discovers her mentor's secret.",
    ),
]


def _provider(settings) -> GeminiProvider:
    return GeminiProvider(
        settings.api_key, settings.model,
        rpm_limit=settings.rpm_limit, rpm_reserve=settings.rpm_reserve,
        tpm_limit=settings.tpm_limit, max_retries=settings.max_retries,
        max_retry_delay=settings.max_retry_delay,
        request_timeout_ms=settings.request_timeout_ms,
        structured_validation_retries=settings.max_artifact_retries,
        embedding_model=settings.embedding_model,
    )


def _proposal(node) -> PlotNodeProposal:
    return PlotNodeProposal(
        location_id=node.location_id, subject=node.subject, verb=node.verb,
        object=node.object, purpose=node.goals[0].purpose,
        narrative_function=node.goals[0].narrative_function,
        taxonomy_id=node.goals[0].taxonomy_id,
        taxonomy_movement_id=node.goals[0].taxonomy_movement_id,
        depends_on_node_ids=node.depends_on_node_ids,
        preconditions=node.preconditions, effects=node.effects,
        intention=node.intention, conflict=node.conflict, consequence=node.consequence,
    )


@pytest.mark.skipif(not LIVE_GEMINI, reason="set RUN_GEMINI_INTEGRATION=1")
@pytest.mark.parametrize("story_request", PROMPTS, ids=["movement", "object", "knowledge"])
def test_gemini_completes_story_with_replayable_cpns(tmp_path, story_request) -> None:
    settings = load_settings()
    provider = _provider(settings)
    schemas = NarrativeSchemaRepository(
        db_path=tmp_path / "taxonomies.sqlite3", provider=provider,
    )
    run = StoryGenerator(
        provider, tmp_path / "stories", schema_repository=schemas,
        max_cpn_retries=settings.max_cpn_retries,
        max_artifact_retries=settings.max_artifact_retries,
    ).generate(story_request)

    assert run.story_path.is_file()
    assert not (run.run_dir / "error_report.json").exists()
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"

    outline = StoryOutlineArtifact.model_validate_json(
        (run.run_dir / "outline.json").read_text(encoding="utf-8")
    )
    storyline = IncrementalStorylineArtifact.model_validate_json(
        (run.run_dir / "storyline.json").read_text(encoding="utf-8")
    )
    anchors = ChapterAnchorsArtifact.model_validate_json(
        (run.run_dir / "chapter_anchors.json").read_text(encoding="utf-8")
    )
    world = WorldArtifact.model_validate_json(
        (run.run_dir / "world.json").read_text(encoding="utf-8")
    )
    characters = CharactersArtifact.model_validate_json(
        (run.run_dir / "characters.json").read_text(encoding="utf-8")
    )
    reviews = json.loads((run.run_dir / "node_reviews.json").read_text(encoding="utf-8"))

    order = {node.id: index for index, node in enumerate(storyline.nodes)}
    assert storyline.topological_order == [node.id for node in storyline.nodes]
    assert all(order[source] < order[node.id]
               for node in storyline.nodes for source in node.depends_on_node_ids)
    accepted_cpns = [node for node in storyline.nodes if node.node_type == "CPN"]
    assert len(reviews["records"]) == len(accepted_cpns)
    assert all(record["review"]["accepted"] for record in reviews["records"])

    cast = characters.storyline_cast()
    graph = NarrativeEntityGraph(world, cast)
    validator = DependencyValidator(world, cast)
    accepted_ids: set[str] = set()
    for node in storyline.nodes:
        report = validator.validate(_proposal(node), graph.snapshot(), accepted_ids)
        assert report.passed, (node.id, [item.model_dump() for item in report.issues])
        graph.apply(node)
        accepted_ids.add(node.id)

    planner = IncrementalPlotPlanner(provider)
    by_chapter = {item.chapter_id: item for item in anchors.anchors}
    for chapter in outline.chapters:
        nodes = [node for node in storyline.nodes if node.chapter_id == chapter.id]
        cpns = [node for node in nodes if node.node_type == "CPN"]
        assert planner.min_cpn_count(chapter) <= len(cpns) <= planner.max_cpn_count(chapter)
        assert [node.node_type for node in nodes].count("CBN") == 1
        assert [node.node_type for node in nodes].count("CEN") == 1
        assert sum(node.target_words for node in nodes) == chapter.target_words
        assert nodes[-1].subject.id == by_chapter[chapter.id].end_subject.id
