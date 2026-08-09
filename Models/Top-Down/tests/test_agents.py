from asg_top_down.agents import AnalystAgent, CharacterDesignerAgent, DirectorAgent, PlannerAgent, WorldBuilderAgent
from asg_top_down.schemas import DirectedStoryArtifact, StoryRequest
from asg_top_down.taxonomies import TaxonomyRepository
from fakes import FakeProvider, RESPONSES


def test_planning_agents_return_storyteller_contracts() -> None:
    provider = FakeProvider()
    taxonomies = TaxonomyRepository()
    request = AnalystAgent(provider).run("Una historia")
    plan = PlannerAgent(provider, taxonomies).run(request)
    world = WorldBuilderAgent(provider).run(request, plan)
    characters = CharacterDesignerAgent(provider, taxonomies).run(request, plan, world)
    archetypes = taxonomies.get_archetypes([plan.archetypes.primary, *plan.archetypes.secondary])
    directed = DirectorAgent(provider).run(request, plan, world, characters, archetypes)
    assert isinstance(directed, DirectedStoryArtifact)
    assert {x.node_type for x in directed.nodes} == {"CBN", "CPN", "CEN"}


def test_defaults_and_sv_normalization() -> None:
    assert RESPONSES[StoryRequest].target_words == 1500
    node = RESPONSES[DirectedStoryArtifact].nodes[0].model_copy(update={"object": ""})
    assert node.model_validate(node.model_dump()).object == node.subject
