"""Regression tests for the Top-Down 3.1 narrative taxonomy system."""

import json
from pathlib import Path

import pytest

from asg_top_down.craft import audit_questions
from asg_top_down.narrative_db import NarrativeSchemaRepository
from asg_top_down.schemas import (
    ChapterPPPBeat, ChapterPPPPlan, CharacterArcPlan, CharacterMilestone,
    CharactersArtifact, GlobalPPPLine, GlobalPPPPlan, GlobalPPPPoint, StoryCraftPlan,
    StoryRequest, TaxonomyApplication, TaxonomyOptionReference, TonePromise,
    TryFailCycle, TryFailPlan,
)


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
        original_prompt=prompt, title="Test", language="español", genre=genre,
        tone="tense", target_words=600, premise="A difficult choice changes the group.",
    )


def application(accent: bool = True) -> TaxonomyApplication:
    return TaxonomyApplication(
        primary_taxonomy_id="heist-caper",
        accent_taxonomy_id="romance" if accent else None,
        selected_promises=[TaxonomyOptionReference(
            taxonomy_id="heist-caper", option_id="promise-impossible-job",
        )],
        selected_roles=[],
        selected_movements=[
            TaxonomyOptionReference(taxonomy_id="heist-caper", option_id="move-proposition"),
            TaxonomyOptionReference(taxonomy_id="heist-caper", option_id="move-operation"),
        ],
        selected_complications=[],
        selected_twist=None,
        selected_conclusion=TaxonomyOptionReference(
            taxonomy_id="heist-caper", option_id="end-costly-win",
        ),
        freshness_choices=["Make the crew solve the decisive barrier through empathy."],
        prompt_evidence=["The request explicitly combines a heist and a central romance."],
        rationale="The operation supplies the main reader promise; romance only colors trust.",
    )


def test_catalog_contains_24_rich_english_profiles_and_sources(tmp_path: Path) -> None:
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    profiles = repository.profiles()
    assert {profile.id for profile in profiles} == EXPECTED_IDS
    assert all(len(profile.sources) >= 2 for profile in profiles)
    assert all(len(profile.movements) >= 4 for profile in profiles)
    assert all(len(profile.complications) >= 3 for profile in profiles)
    narrative = json.dumps(
        [profile.model_dump(mode="json", exclude={"sources"}) for profile in profiles],
        ensure_ascii=False,
    )
    assert not set("¿¡").intersection(narrative)
    for spanish_phrase in ("el protagonista", "la historia", "debe ", "hacia ", "sin dejar"):
        assert spanish_phrase not in narrative.casefold()


def test_spanish_recognition_is_separate_and_heist_romance_is_explicit(tmp_path: Path) -> None:
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    blueprint = repository.retrieve(request(
        "atraco con romance", "Una banda prepara un atraco y surge un romance entre dos miembros.",
    ))
    assert [item.profile.id for item in blueprint.candidates[:2]] == ["heist-caper", "romance"]
    assert all(item.explicit_match for item in blueprint.candidates[:2])
    heist = blueprint.candidates[0].profile
    assert "atraco" not in json.dumps(heist.model_dump(mode="json"), ensure_ascii=False).casefold()
    assert "atraco" not in json.dumps(blueprint.model_context(), ensure_ascii=False).casefold()


def test_enriched_prompt_improves_ranking_without_becoming_explicit_evidence(tmp_path: Path) -> None:
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    enriched = request("heist", "A crew prepares a difficult vault theft.").model_copy(update={
        "processed_prompt": (
            "Write a heist in which a central romance complicates trust inside the crew."
        ),
    })
    blueprint = repository.retrieve(enriched)
    romance = next(item for item in blueprint.candidates if item.profile.id == "romance")
    assert romance.explicit_match is False
    assert "romance" not in romance.matched_terms
    assert "central romance" in blueprint.trace.query


def test_application_is_flexible_compiles_an_english_brief_and_adds_audits(tmp_path: Path) -> None:
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    blueprint = repository.retrieve(request(
        "heist romance", "Write a heist with a central romance between two crew members.",
    ))
    chosen = application()
    repository.validate_application(chosen, blueprint)
    brief = repository.compile_brief(chosen, blueprint)
    assert brief.primary_taxonomy == "Heist / Caper"
    assert brief.accent_taxonomy == "Romance"
    assert brief.twist is None
    assert brief.roles == []
    assert all("atraco" not in value.casefold() for value in brief.reader_promises)

    global_ppp = GlobalPPPPlan(
        tone_promise=TonePromise(description="Tense", opening_signal="Risk",
                                 continuity_rule="Escalate"),
        primary_line=GlobalPPPLine(
            id="master", kind="plot", subject="crew",
            promise=GlobalPPPPoint(id="p", chapter_id="chapter-001",
                                   description="The vault", reader_effect="Expect entry"),
            progress=[GlobalPPPPoint(id="g", chapter_id="chapter-001",
                                     description="The attempt", reader_effect="Feel progress")],
            payoff=GlobalPPPPoint(id="o", chapter_id="chapter-001",
                                  description="The cost", reader_effect="Feel resolution"),
        ),
    )
    craft = StoryCraftPlan(
        global_ppp=global_ppp,
        character_arcs=CharacterArcPlan(milestones=[CharacterMilestone(
            character_name="A", chapter_id="chapter-001", stage="start",
            description="A hesitates",
        )]),
        try_fail=TryFailPlan(cycles=[
            TryFailCycle(id="t1", chapter_id="chapter-001", action="Enter",
                         outcome="yes_but", consequence="Alarm"),
            TryFailCycle(id="t2", chapter_id="chapter-001", action="Escape",
                         outcome="no_and", consequence="Lockdown"),
        ]),
        chapters=[ChapterPPPPlan(
            chapter_id="chapter-001",
            promise=ChapterPPPBeat(description="Enter", node_ids=["n_0001"]),
            progress=[ChapterPPPBeat(description="Adapt", node_ids=["n_0002"])],
            payoff=ChapterPPPBeat(description="Leave", node_ids=["n_0003"]),
            advances_global_point_ids=["p", "g", "o"],
        )],
    )
    questions = audit_questions(
        request("heist", "Write a heist."), craft,
        CharactersArtifact(characters=[{
            "name": "A", "narrative_role": "lead", "jungian_archetype": "explorer",
            "goal": "open vault", "motivation": "need", "conflict": "security", "arc": "change",
        }]),
        brief,
    )
    promise = next(item for item in questions if item["question_id"] == "taxonomy:promise:1")
    quality = next(item for item in questions if item["question_id"] == "taxonomy:quality:1")
    language = next(item for item in questions if item["question_id"] == "language:output")
    assert promise["blocking"] is True
    assert quality["blocking"] is False
    assert language["blocking"] is True


def test_accent_requires_explicit_evidence(tmp_path: Path) -> None:
    repository = NarrativeSchemaRepository(db_path=tmp_path / "taxonomy.sqlite3")
    blueprint = repository.retrieve(request("heist", "A crew plans a difficult vault theft."))
    profiles = {item.profile.id for item in blueprint.candidates}
    if "romance" not in profiles:
        romance = repository.profile("romance")
        blueprint.candidates[-1] = blueprint.candidates[-1].model_copy(update={
            "profile": romance, "explicit_match": False,
        })
    with pytest.raises(ValueError, match="explicit prompt evidence"):
        repository.validate_application(application(), blueprint)


def test_seed_reconciliation_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "taxonomy.sqlite3"
    first = NarrativeSchemaRepository(db_path=path)
    second = NarrativeSchemaRepository(db_path=path)
    assert [item.id for item in first.profiles()] == [item.id for item in second.profiles()]


class EmbeddingProvider:
    embedding_model_name = "taxonomy-test-embedding"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.document_calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        if self.fail:
            raise RuntimeError("offline")
        return [[1.0, float(index % 2)] for index, _ in enumerate(texts)]

    def embed_query(self, _text: str) -> list[float]:
        if self.fail:
            raise RuntimeError("offline")
        return [1.0, 0.0]


def test_embeddings_are_cached_and_failure_falls_back_locally(tmp_path: Path) -> None:
    path = tmp_path / "taxonomy.sqlite3"
    first_provider = EmbeddingProvider()
    first = NarrativeSchemaRepository(db_path=path, provider=first_provider)
    result = first.retrieve(request("heist", "A crew prepares a vault heist."))
    assert result.trace.used_embeddings is True
    assert first_provider.document_calls == 1

    cached_provider = EmbeddingProvider()
    cached = NarrativeSchemaRepository(db_path=path, provider=cached_provider)
    cached_result = cached.retrieve(request("heist", "A crew prepares a vault heist."))
    assert cached_result.trace.used_embeddings is True
    assert cached_provider.document_calls == 0

    offline = NarrativeSchemaRepository(
        db_path=tmp_path / "offline.sqlite3", provider=EmbeddingProvider(fail=True),
    )
    offline_result = offline.retrieve(request("atraco", "Una banda prepara un atraco."))
    assert offline_result.trace.used_embeddings is False
    assert offline_result.candidates[0].profile.id == "heist-caper"
