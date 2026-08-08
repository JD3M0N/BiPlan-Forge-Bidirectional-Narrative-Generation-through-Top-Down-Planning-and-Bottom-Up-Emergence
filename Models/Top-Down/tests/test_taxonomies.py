from asg_top_down.taxonomies import TaxonomyRepository


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
