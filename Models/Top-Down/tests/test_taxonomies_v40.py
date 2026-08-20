"""Regression tests for the current taxonomy repository (no legacy catalog)."""

import json
from pathlib import Path

import pytest

from asg_top_down.narrative_db import NarrativeSchemaRepository
from asg_top_down.schemas import StoryRequest, TaxonomyApplication, TaxonomyOptionReference


EXPECTED_IDS = {
    "heist-caper", "whodunit-mystery", "conspiracy-political-thriller",
    "cat-and-mouse-thriller", "courtroom-legal-drama", "revenge",
    "escape-prison-break", "rescue-mission", "survival", "disaster",
    "expedition-adventure", "fantasy-quest", "war-mission", "western-frontier",
    "first-contact", "dystopian-rebellion", "monster-creature-horror",
    "gothic-horror", "psychological-horror", "romance", "romantic-comedy",
    "coming-of-age", "family-domestic-drama", "sports-underdog",
}


def request(genre: str, prompt: str) -> StoryRequest:
    return StoryRequest(
        original_prompt=prompt, processed_prompt=prompt, title="Test", language="Spanish",
        genre=genre, tone="tense", target_words=600,
        premise="A difficult choice changes the group.",
    )


def application(accent: bool = True) -> TaxonomyApplication:
    return TaxonomyApplication(
        primary_taxonomy_id="heist-caper",
        accent_taxonomy_id="romance" if accent else None,
        selected_promises=[TaxonomyOptionReference(
            taxonomy_id="heist-caper", option_id="promise-impossible-job",
        )],
        selected_movements=[
            TaxonomyOptionReference(taxonomy_id="heist-caper", option_id="move-proposition"),
            TaxonomyOptionReference(taxonomy_id="heist-caper", option_id="move-operation"),
        ],
        selected_conclusion=TaxonomyOptionReference(
            taxonomy_id="heist-caper", option_id="end-costly-win",
        ),
        freshness_choices=["Solve the decisive barrier through empathy."],
        prompt_evidence=["The request explicitly combines a heist and a romance."],
        rationale="The operation is primary; romance colors trust.",
    )


def test_repository_contains_24_current_profiles_and_drops_legacy_tables(tmp_path: Path) -> None:
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    assert {profile.id for profile in repository.profiles()} == EXPECTED_IDS
    with repository._connect() as db:
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert "catalog_entry" not in tables
    assert "beat" not in tables


def test_spanish_recognition_is_separate_and_explicit(tmp_path: Path) -> None:
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    blueprint = repository.retrieve(request(
        "atraco con romance", "Una banda prepara un atraco y surge un romance.",
    ))
    assert [item.profile.id for item in blueprint.candidates[:2]] == ["heist-caper", "romance"]
    assert all(item.explicit_match for item in blueprint.candidates[:2])
    assert "atraco" not in json.dumps(blueprint.model_context(), ensure_ascii=False).casefold()


def test_application_compiles_a_flexible_brief(tmp_path: Path) -> None:
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    blueprint = repository.retrieve(request(
        "heist romance", "Write a heist with a central romance.",
    ))
    chosen = application()
    repository.validate_application(chosen, blueprint)
    brief = repository.compile_brief(chosen, blueprint)
    assert brief.primary_taxonomy == "Heist / Caper"
    assert brief.accent_taxonomy == "Romance"
    assert brief.twist is None
    assert brief.roles == []


def test_non_explicit_accent_is_rejected(tmp_path: Path) -> None:
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    blueprint = repository.retrieve(request("heist", "Write a difficult vault theft."))
    with pytest.raises(ValueError, match="explicit"):
        repository.validate_application(application(), blueprint)
