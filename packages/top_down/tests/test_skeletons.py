import math
import re

import pytest
from asg_top_down.schemas import (
    ID_PATTERN,
    NarrativeBlueprint,
    RoleSuggestion,
    SemanticSkeletonRanking,
    SemanticSkeletonScore,
    SkeletonMatch,
    StoryRequest,
)
from asg_top_down.skeleton_match import (
    FALLBACK_SHORTLIST,
    LEXICAL_WEIGHT,
    SEMANTIC_WEIGHT,
    lexical_scores,
    normalize,
    rank_skeletons,
    skeleton_query,
)
from asg_top_down.skeletons import (
    PLOT_SKELETONS,
    SKELETONS_BY_ID,
    FunctionalRole,
    Layer,
    blueprint_guidance,
    find_skeleton,
    skeletons_for_layer,
)


def make_request() -> StoryRequest:
    return StoryRequest(
        original_prompt="Escribe una historia sobre un robo en un museo vigilado",
        processed_prompt="Write a story about a theft in a guarded museum.",
        title="The Price of Truth",
        language="Spanish",
        genre="drama",
        tone="tense",
        narrative_profile="essential",
        premise="A thief steals a relic from a guarded museum to save his sister.",
        constraints=[],
        creative_directions=[],
    )


class RankingProvider:
    """Return one fixed semantic ranking, or raise, without touching the network."""

    def __init__(self, scores=None, *, fail=False) -> None:
        self.scores = scores or {}
        self.fail = fail
        self.calls = 0

    def generate_structured(self, *, system_instruction, prompt, schema, profile):
        self.calls += 1
        if self.fail:
            raise RuntimeError("semantic ranking unavailable")
        return SemanticSkeletonRanking(
            scores=[
                SemanticSkeletonScore(skeleton_id=key, relevance=value)
                for key, value in self.scores.items()
            ]
        )


def test_catalog_is_internally_consistent() -> None:
    """IDs are unique and well-formed, and every cross-reference resolves."""
    assert len(PLOT_SKELETONS) >= 20
    ids = [item.id for item in PLOT_SKELETONS]
    assert len(set(ids)) == len(ids)
    valid_roles = {role.value for role in FunctionalRole}
    for item in PLOT_SKELETONS:
        assert re.fullmatch(ID_PATTERN, item.id), item.id
        assert {role.value for role in item.typical_functional_roles} <= valid_roles
        for reference in (*item.pairs_well_with, *item.tensions_with):
            assert reference in SKELETONS_BY_ID
            assert reference != item.id
    subplot_only = [item for item in PLOT_SKELETONS if item.layers == (Layer.SUBPLOT,)]
    assert len(subplot_only) >= 6
    assert len(skeletons_for_layer(Layer.MACROPLOT)) >= 20
    for reference in FALLBACK_SHORTLIST:
        assert reference in SKELETONS_BY_ID


def test_catalog_entry_hides_thesis_only_attribution() -> None:
    entry = find_skeleton("heist").catalog_entry()
    assert "influences" not in entry
    assert entry["id"] == "heist"


def test_lexical_scoring_is_deterministic_and_ranks_the_obvious_shape() -> None:
    query = "A thief must steal a relic from a guarded museum to save his sister"
    first = lexical_scores(query)
    second = lexical_scores(query)
    assert [(row.skeleton_id, row.score) for row in first] == [
        (row.skeleton_id, row.score) for row in second
    ]
    ranked = rank_skeletons(query, limit=5)
    assert ranked[0].skeleton_id == "heist"
    assert "rescue" in {row.skeleton_id for row in ranked}


def test_normalize_strips_spanish_accents() -> None:
    assert normalize("Una traición en la prisión") == "una traicion en la prision"


def test_spanish_request_fields_still_rank_from_the_english_brief() -> None:
    """The analyst leaves premise, genre and tone in Spanish for Spanish stories."""
    request = StoryRequest(
        original_prompt="Escribe un relato sobre una fuga de una prision en una isla",
        processed_prompt=(
            "A political prisoner studies the guard rotation for months to escape a prison "
            "on an island, and discovers his only route out condemns his cellmate."
        ),
        title="La Marea de Piedra",
        language="Spanish",
        genre="Suspense / Drama Carcelario",
        tone="tenso y sobrio",
        narrative_profile="essential",
        premise="Un preso politico planea su fuga de una prision en una isla.",
        constraints=[],
        creative_directions=[],
    )
    ranked = rank_skeletons(skeleton_query(request), limit=3)
    assert ranked[0].skeleton_id == "escape"
    assert ranked[0].lexical_score > 0.5


def test_empty_query_returns_the_varied_fallback_shortlist() -> None:
    ranked = rank_skeletons("", limit=8)
    assert [row.skeleton_id for row in ranked] == list(FALLBACK_SHORTLIST[:8])
    assert all(row.semantic_score is None for row in ranked)


@pytest.mark.parametrize(
    "provider",
    [RankingProvider(fail=True), RankingProvider({"not_a_skeleton": 1.0})],
    ids=["semantic-call-fails", "semantic-call-names-an-unknown-skeleton"],
)
def test_semantic_degradation_never_raises(provider) -> None:
    """A failing provider or an unresolvable skeleton id degrades to lexical-only, never raises."""
    ranked = rank_skeletons("a detective investigates a murder", provider=provider)
    assert ranked
    assert all(row.semantic_score is None for row in ranked)


def test_semantic_blend_uses_the_declared_weights() -> None:
    query = "A thief must steal a relic from a guarded museum"
    lexical = {row.skeleton_id: row.lexical_score for row in lexical_scores(query)}
    provider = RankingProvider({"mystery": 1.0})
    ranked = rank_skeletons(query, provider=provider, limit=len(PLOT_SKELETONS))
    scored = {row.skeleton_id: row for row in ranked}
    mystery = scored["mystery"]
    assert mystery.semantic_score == 1.0
    expected = LEXICAL_WEIGHT * lexical["mystery"] + SEMANTIC_WEIGHT * 1.0
    assert math.isclose(mystery.score, expected, rel_tol=1e-9)
    heist = scored["heist"]
    assert heist.semantic_score == 0.0
    assert math.isclose(heist.score, LEXICAL_WEIGHT * lexical["heist"], rel_tol=1e-9)


def test_skeleton_query_leads_with_processed_prompt_and_skips_the_original() -> None:
    request = make_request()
    query = skeleton_query(request)
    assert request.processed_prompt in query
    assert request.premise in query
    assert request.original_prompt not in query


def blueprint(**overrides) -> NarrativeBlueprint:
    payload = {
        "macroplot_id": "heist",
        "macroplot_reading": "The theft is a way of paying an older debt.",
        "subplot_ids": ["infiltration"],
        "role_suggestions": [
            RoleSuggestion(functional_role="helper", persona="thief", sketch="opens the way")
        ],
        "unexpected_angle": "The vault is already empty when they arrive.",
        "considered": [
            SkeletonMatch(
                skeleton_id="heist",
                score=0.9,
                lexical_score=0.9,
                catalog_order=0,
            )
        ],
    }
    payload.update(overrides)
    return NarrativeBlueprint(**payload)


def test_guidance_is_phrased_as_optional_and_tolerates_unknown_ids() -> None:
    """Guidance reads as non-binding inspiration and never raises on an invented skeleton id."""
    text = blueprint_guidance(blueprint())
    assert "non-binding" in text
    assert "must" not in text.casefold()
    assert "The vault is already empty when they arrive." in text
    assert "helper" in text

    unknown = blueprint_guidance(blueprint(macroplot_id="not_a_skeleton", subplot_ids=["nope"]))
    assert "not_a_skeleton" in unknown
    assert "none in particular" in unknown
