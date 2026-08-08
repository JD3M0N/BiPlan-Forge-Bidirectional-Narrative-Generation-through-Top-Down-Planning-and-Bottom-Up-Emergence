from asg_top_down.agents import AnalystAgent, CharacterDesignerAgent, DirectorAgent, PlannerAgent, WorldBuilderAgent
from asg_top_down.schemas import CharactersArtifact, DirectedStoryArtifact, StoryPlanArtifact, StoryRequest, WorldArtifact
from asg_top_down.taxonomies import TaxonomyRepository
from fakes import FakeProvider, RESPONSES


def test_planning_agents_return_v2_contracts() -> None:
    provider = FakeProvider()
    taxonomies = TaxonomyRepository()
    request = AnalystAgent(provider).run("Una historia")
    plan = PlannerAgent(provider, taxonomies).run(request)
    world = WorldBuilderAgent(provider).run(request, plan)
    characters = CharacterDesignerAgent(provider, taxonomies).run(request, plan, world)
    directed = DirectorAgent(provider).run(request, plan, world, characters)
    assert isinstance(request, StoryRequest)
    assert isinstance(plan, StoryPlanArtifact)
    assert isinstance(world, WorldArtifact)
    assert isinstance(characters, CharactersArtifact)
    assert isinstance(directed, DirectedStoryArtifact)


def test_defaults_and_secondary_limit() -> None:
    request = RESPONSES[StoryRequest]
    assert request.language == "español" and request.target_words == 1500
    assert len(RESPONSES[StoryPlanArtifact].archetypes.secondary) <= 2
