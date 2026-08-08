import pytest

from asg_top_down.taxonomies import TaxonomyRepository


class SemanticProvider:
    model_name = "semantic-fake"

    def __init__(self, scores: dict[str, float], invalid_attempts: int = 0) -> None:
        self.scores = scores
        self.invalid_attempts = invalid_attempts
        self.calls = 0

    def generate_structured(self, *, system_instruction, prompt, schema):
        self.calls += 1
        values = list(self.scores.items())
        if self.calls <= self.invalid_attempts:
            values = values[:-1]
        return schema.model_validate({
            "scores": [
                {"archetype_id": archetype_id, "relevance": relevance}
                for archetype_id, relevance in values
            ]
        })


class FailingSemanticProvider:
    model_name = "failing-fake"

    def __init__(self) -> None:
        self.calls = 0

    def generate_structured(self, **kwargs):
        self.calls += 1
        raise RuntimeError("fallo semantico")


def test_taxonomy_catalogs_are_complete_and_resolve_spanish_aliases() -> None:
    repository = TaxonomyRepository()
    assert len(repository.archetypes) == 24
    assert len(repository.roles) == 12
    assert repository.resolve_archetype("búsqueda").id == "quest"
    assert len({x.id for x in repository.archetypes}) == 24
    role_ids = {x.id for x in repository.roles}
    for archetype in repository.archetypes:
        assert set(archetype.frequent_roles) <= role_ids


def test_taxonomy_repository_returns_a_compact_relevant_shortlist() -> None:
    repository = TaxonomyRepository()
    selected = repository.recommend_archetypes("Un detective investiga un misterio y un enigma")
    assert selected[0].id == "mystery"
    assert len(selected) < len(repository.archetypes)


def test_taxonomy_scores_expose_every_value_and_matching_term() -> None:
    repository = TaxonomyRepository()
    scores = repository.score_archetypes("Un misterio sobre un enigma")
    assert len(scores) == 24
    assert scores[0].archetype_id == "mystery"
    assert 0 < scores[0].score <= 1
    assert scores[0].score == scores[0].lexical_score
    assert scores[0].semantic_score is None
    assert scores[0].matched_terms == ["enigma", "misterio"]


def test_scores_are_bounded_sorted_and_best_match_is_first() -> None:
    repository = TaxonomyRepository()
    scores = repository.score_archetypes("Una misiÃ³n de amor y misterio")
    assert len({row.archetype_id for row in scores}) == 24
    assert all(0 <= row.score <= 1 for row in scores)
    assert all(0 <= row.lexical_score <= 1 for row in scores)
    assert [row.score for row in scores] == sorted(
        (row.score for row in scores), reverse=True
    )
    assert repository.best_archetype_match("Una misiÃ³n de amor y misterio").archetype_id == scores[0].archetype_id


def test_empty_prompt_is_deterministic_and_does_not_call_provider() -> None:
    base = TaxonomyRepository()
    provider = SemanticProvider({item.id: 0.5 for item in base.archetypes})
    repository = TaxonomyRepository(provider=provider)
    scores = repository.score_archetypes("")
    assert provider.calls == 0
    assert all(row.score == 0 for row in scores)
    assert scores[0].catalog_order == 0


def test_hybrid_score_uses_seventy_thirty_weighting() -> None:
    lexical_repository = TaxonomyRepository()
    lexical = {
        row.archetype_id: row.lexical_score
        for row in lexical_repository.score_archetypes("misterio enigma")
    }
    semantic = {item.id: 0.2 for item in lexical_repository.archetypes}
    semantic["mystery"] = 0.8
    repository = TaxonomyRepository(provider=SemanticProvider(semantic))
    result = next(
        row for row in repository.score_archetypes("misterio enigma")
        if row.archetype_id == "mystery"
    )
    assert result.semantic_score == 0.8
    assert result.score == pytest.approx(0.7 * lexical["mystery"] + 0.3 * 0.8)


def test_invalid_semantic_ranking_retries_once_then_succeeds() -> None:
    base = TaxonomyRepository()
    provider = SemanticProvider(
        {item.id: 0.4 for item in base.archetypes}, invalid_attempts=1
    )
    scores = TaxonomyRepository(provider=provider).score_archetypes("aventura")
    assert provider.calls == 2
    assert all(row.semantic_score == 0.4 for row in scores)


def test_two_semantic_failures_fall_back_to_lexical_scores() -> None:
    provider = FailingSemanticProvider()
    scores = TaxonomyRepository(provider=provider).score_archetypes("misterio")
    assert provider.calls == 2
    assert all(row.semantic_score is None for row in scores)
    assert all(row.score == row.lexical_score for row in scores)
