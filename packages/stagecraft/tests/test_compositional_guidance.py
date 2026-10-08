import json

import pytest
from asg_stagecraft import StoryGenerator
from asg_stagecraft.agents.base import story_specification_header
from asg_stagecraft.planning.catalog import PLOT_SKELETONS
from asg_stagecraft.planning.guidance_composition import compose_patterns, validate_composition
from asg_stagecraft.planning.guidance_models import (
    CompositionArtifact,
    CompositionDraft,
    CompositionFailure,
    RetrievalDraft,
)
from asg_stagecraft.planning.guidance_retrieval import retrieve_patterns
from asg_stagecraft.planning.profiles import NarrativeProfile
from asg_stagecraft.runtime.errors import (
    ConfigurationError,
    GeminiDailyQuotaError,
    RunCancelledError,
)
from test_generator_v5 import FakeProvider, make_request


def judgments(**overrides):
    rows = [
        {
            "skeleton_id": entry.id,
            "relevance": 0.1,
            "status": "weak",
            "evidence": "Only a speculative fit.",
        }
        for entry in PLOT_SKELETONS
    ]
    for row in rows:
        row.update(overrides.get(row["skeleton_id"], {}))
    return RetrievalDraft(judgments=rows)


def composition(skeleton="mystery", **overrides):
    return CompositionDraft.model_validate(
        {
            "reason": "The missing records force a choice between truth and loyalty.",
            "selections": [
                {
                    "skeleton_id": skeleton,
                    "scope": "principal",
                    "evidence": "The request describes a missing record.",
                    "contribution": "Each discovery puts a trusted colleague at risk.",
                    "connection": (
                        "The investigation makes institutional survival depend on hiding the truth."
                    ),
                }
            ],
            "role_suggestions": [
                {
                    "functional_role": "helper",
                    "persona": "archivist",
                    "sketch": "Protects a friend.",
                }
            ],
            "movements": [
                {
                    "skeleton_id": skeleton,
                    "source_index": 0,
                    "adaptation": "The record changes who can safely speak.",
                }
            ],
            **overrides,
        }
    )


class GuidanceProvider(FakeProvider):
    def __init__(self, retrievals=None, compositions=None):
        super().__init__()
        self.retrievals = list(retrievals or [judgments(mystery={"status": "pertinent"})])
        self.compositions = list(compositions or [composition()])

    def generate_structured(self, *, system_instruction, prompt, schema, profile):
        queue = {RetrievalDraft: self.retrievals, CompositionDraft: self.compositions}.get(schema)
        if queue is None:
            return super().generate_structured(
                system_instruction=system_instruction, prompt=prompt, schema=schema, profile=profile
            )
        self.structured_calls.append((schema.__name__, system_instruction, prompt))
        result = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(result, Exception):
            raise result
        return result


def test_semantic_order_and_explicit_conflicts_outrank_words():
    request = make_request().model_copy(
        update={
            "processed_prompt": "No romance, no love triangle. A detective investigates a murder.",
            "constraints": ["No romance or love triangle."],
        }
    )
    response = judgments(
        mystery={"status": "pertinent", "relevance": 0.9},
        reunion={"status": "pertinent", "relevance": 1.0},
        love={"status": "incompatible", "constraint_indices": [0]},
    )
    provider = GuidanceProvider(retrievals=[response])
    result = retrieve_patterns(request, provider)
    assert [row.skeleton_id for row in result.candidates] == ["reunion", "mystery"]
    assert result.candidates[0].lexical_score < result.candidates[1].lexical_score
    prompt = json.loads(provider.structured_calls[0][2])
    assert prompt["request"]["constraints"] == request.constraints
    assert "original_prompt" not in prompt["request"]
    assert not result.degraded


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "duplicate",
        "unknown",
        "invalid-constraint",
        "missing-constraint",
        "supporting-constraint",
        "duplicate-constraint",
    ],
)
def test_incomplete_or_inconsistent_retrieval_is_repaired(fault):
    bad = judgments().model_dump()
    if fault == "missing":
        bad["judgments"].pop()
    elif fault == "duplicate":
        bad["judgments"][0] = bad["judgments"][1]
    elif fault == "unknown":
        bad["judgments"][0]["skeleton_id"] = "invented"
    elif fault == "missing-constraint":
        bad["judgments"][0].update(status="incompatible", constraint_indices=[])
    elif fault == "supporting-constraint":
        bad["judgments"][0].update(status="pertinent", constraint_indices=[0])
    elif fault == "duplicate-constraint":
        bad["judgments"][0].update(status="incompatible", constraint_indices=[0, 0])
    else:
        bad["judgments"][0].update(status="incompatible", constraint_indices=[900])
    provider = GuidanceProvider(retrievals=[RetrievalDraft.model_validate(bad), judgments()])
    result = retrieve_patterns(make_request(), provider)
    assert result.attempts == 2 and result.diagnostics and not result.degraded
    assert "GUIDANCE CORRECTION" in provider.structured_calls[1][2]
    assert len(result.judgments) == len(PLOT_SKELETONS)
    assert result.rejected_drafts == [bad]


@pytest.mark.parametrize(
    "query", ["", "Un preso escapa de una prisión.", "An island prison escape."]
)
def test_unavailable_semantics_abstains_without_composition_call(query):
    request = make_request().model_copy(
        update={"processed_prompt": query, "premise": "", "title": " "}
    )
    provider = GuidanceProvider(retrievals=[RuntimeError("private provider detail")])
    result = retrieve_patterns(request, provider)
    assert result.degraded and result.attempts == 2 and not result.candidates
    calls = len(provider.structured_calls)
    composed = compose_patterns(request, result, provider)
    assert composed.abstained and composed.reason == "retrieval_failed"
    assert not composed.character_block and not composed.planning_block
    assert composed.attempts == 0 and len(provider.structured_calls) == calls
    assert "private provider detail" not in result.model_dump_json()
    assert len(result.catalog_snapshot) == len(PLOT_SKELETONS)


@pytest.mark.parametrize("stage", ["retrieval", "composition"])
@pytest.mark.parametrize("error", [ConfigurationError, GeminiDailyQuotaError, RunCancelledError])
def test_non_degradable_errors_escape_both_stages(stage, error):
    provider = GuidanceProvider(
        retrievals=[error("stop")] if stage == "retrieval" else None,
        compositions=[error("stop")] if stage == "composition" else None,
    )
    with pytest.raises(error):
        retrieval = retrieve_patterns(make_request(), provider)
        compose_patterns(make_request(), retrieval, provider)


@pytest.mark.parametrize("skeleton", ["heist", "reunion"])
def test_typical_subplot_can_carry_the_whole_story(skeleton):
    provider = GuidanceProvider(
        retrievals=[judgments(**{skeleton: {"status": "pertinent"}})],
        compositions=[composition(skeleton)],
    )
    request = make_request()
    result = compose_patterns(request, retrieve_patterns(request, provider), provider)
    assert isinstance(result, CompositionArtifact)
    assert result.selections[0].scope == "principal"
    assert result.deviation is None
    prompt = json.loads(provider.structured_calls[-1][2])
    pattern = prompt["candidates"][0]["pattern"]
    assert pattern["typical_functional_roles"] and pattern["pairs_well_with"]
    assert "influences" not in pattern


@pytest.mark.parametrize(
    ("profile", "scopes", "valid"),
    [
        ("essential", ["principal", "local"], True),
        ("essential", ["secondary"], False),
        ("essential", ["local", "local"], False),
        ("developed", ["principal", "secondary", "local"], True),
        ("developed", ["secondary", "secondary"], False),
        ("expansive", ["principal", "secondary", "local", "local"], True),
        ("expansive", ["local", "local", "local", "local"], False),
        ("essential", ["principal", "principal"], False),
    ],
)
def test_scope_limits_are_ceilings_not_quotas(profile, scopes, valid):
    request = make_request().model_copy(update={"narrative_profile": NarrativeProfile(profile)})
    retrieval = retrieve_patterns(request, GuidanceProvider(retrievals=[judgments()]))
    selections = [
        {
            "skeleton_id": row.skeleton_id,
            "scope": scope,
            "evidence": "The premise supports this choice.",
            "contribution": "Adds a conflicting loyalty.",
            "connection": "The loyalty obstructs the investigation.",
        }
        for row, scope in zip(retrieval.candidates, scopes, strict=False)
    ]
    draft = composition(selections=selections, movements=[])
    if valid:
        validate_composition(draft, request, retrieval)
    else:
        with pytest.raises(ValueError):
            validate_composition(draft, request, retrieval)


@pytest.mark.parametrize("fault", ["unknown", "duplicate", "source", "abstention"])
def test_context_invalid_composition_is_repaired_then_failure_is_distinct(fault):
    draft = composition().model_dump()
    if fault == "unknown":
        draft["selections"][0]["skeleton_id"] = "invented"
    elif fault == "duplicate":
        draft["selections"].append(draft["selections"][0])
    elif fault == "source":
        draft["movements"][0]["source_index"] = 999
    else:
        draft["abstained"] = True
    provider = GuidanceProvider(compositions=[CompositionDraft.model_validate(draft)])
    request = make_request()
    retrieval = retrieve_patterns(request, provider)
    failed = compose_patterns(request, retrieval, provider)
    assert isinstance(failed, CompositionFailure)
    assert len(failed.diagnostics) == 2
    provider.compositions = [CompositionDraft.model_validate(draft), composition()]
    repaired = compose_patterns(request, retrieval, provider)
    assert isinstance(repaired, CompositionArtifact) and repaired.attempts == 2
    repair_prompt = provider.structured_calls[-1][2]
    assert "PREVIOUS GUIDANCE (data to correct)" in repair_prompt
    assert '"selections"' in repair_prompt


@pytest.mark.parametrize("outcome", ["guided", "abstained", "failed", "degraded"])
def test_pipeline_records_evidence_and_injects_only_frozen_audience_blocks(tmp_path, outcome):
    responses = {
        "guided": composition(),
        "abstained": CompositionDraft(abstained=True, reason="The premise needs no extra shape."),
        "failed": RuntimeError("unavailable"),
        "degraded": composition(),
    }
    provider = GuidanceProvider(
        compositions=[responses[outcome]],
        retrievals=[RuntimeError("unavailable")] if outcome == "degraded" else None,
    )
    run = StoryGenerator(
        provider, tmp_path, guidance_strategy="compositional_v2", audio=False
    ).generate(make_request())
    retrieval = json.loads((run.run_dir / "narrative_retrieval.json").read_text(encoding="utf-8"))
    assert retrieval["catalog_hash"] and retrieval["catalog_snapshot"]
    assert retrieval["degraded"] == (outcome == "degraded")
    if outcome == "failed":
        assert not (run.run_dir / "narrative_blueprint.json").exists()
        assert (run.run_dir / "narrative_composition_error.json").exists()
        return
    artifact = CompositionArtifact.model_validate_json(
        (run.run_dir / "narrative_blueprint.json").read_text(encoding="utf-8")
    )
    if outcome in {"abstained", "degraded"}:
        assert not artifact.character_block and not artifact.planning_block
        assert all(
            "NARRATIVE INSPIRATION" not in prompt for _, _, prompt in provider.structured_calls
        )
    else:
        for name, _, prompt in provider.structured_calls:
            if name == "CharactersArtifact":
                assert artifact.character_block in prompt
                assert artifact.movements[0].adaptation not in prompt
            elif name == "StoryPlanDraft":
                assert artifact.planning_block in prompt
            else:
                assert "NARRATIVE INSPIRATION" not in prompt
        assert artifact.planning_block in story_specification_header(make_request(), artifact)
        assert all("NARRATIVE INSPIRATION" not in prompt for _, prompt in provider.text_calls)


def test_disabling_either_strategy_preserves_all_provider_prompts(tmp_path):
    providers = [GuidanceProvider(), GuidanceProvider()]
    for strategy, provider in zip(["hybrid_v1", "compositional_v2"], providers, strict=True):
        run = StoryGenerator(
            provider,
            tmp_path / strategy,
            guidance_strategy=strategy,
            narrative_guidance=False,
            audio=False,
        ).generate(make_request())
        assert not (run.run_dir / "narrative_retrieval.json").exists()
    assert providers[0].structured_calls == providers[1].structured_calls
    assert providers[0].text_calls == providers[1].text_calls


@pytest.mark.parametrize("connection", [None, "", "   "])
def test_new_selections_require_connection_but_old_artifacts_remain_readable(connection):
    from asg_stagecraft.runtime.provider import _gemini_response_schema
    from pydantic import ValidationError

    payload = composition().model_dump()
    if connection is None:
        payload["selections"][0].pop("connection")
    else:
        payload["selections"][0]["connection"] = connection
    with pytest.raises(ValidationError):
        CompositionDraft.model_validate(payload)
    wire = _gemini_response_schema(CompositionDraft)["$defs"]["PatternSelectionDraft"]
    assert "connection" in wire["required"]
    assert wire["properties"]["connection"]["minLength"] == 1
    payload["selections"][0]["connection"] = ""
    historical = CompositionArtifact.model_validate(
        {**payload, "catalog_version": "1", "catalog_hash": "old", "catalog_snapshot": []}
    )
    assert historical.selections[0].connection == ""


def test_valid_empty_retrieval_abstains_and_old_artifacts_remain_readable():
    from asg_stagecraft.planning.guidance_models import RetrievalArtifact

    provider = GuidanceProvider()
    request = make_request()
    retrieval = retrieve_patterns(request, provider)
    payload = retrieval.model_dump()
    payload.pop("rejected_drafts")
    payload["candidates"] = []
    historical = RetrievalArtifact.model_validate(payload)
    assert historical.rejected_drafts == []
    calls = len(provider.structured_calls)
    result = compose_patterns(request, historical, provider)
    assert result.abstained and result.reason == "no_eligible_candidates"
    assert len(provider.structured_calls) == calls


def test_semantic_ties_use_catalog_order_not_words():
    request = make_request().model_copy(
        update={"processed_prompt": "reunion estranged family", "premise": "", "title": " "}
    )
    provider = GuidanceProvider(
        retrievals=[
            judgments(
                quest={"status": "pertinent", "relevance": 0.8},
                reunion={"status": "pertinent", "relevance": 0.8},
            )
        ]
    )
    result = retrieve_patterns(request, provider)
    assert [c.skeleton_id for c in result.candidates] == ["quest", "reunion"]
    assert result.candidates[0].lexical_score < result.candidates[1].lexical_score
