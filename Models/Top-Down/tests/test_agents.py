from asg_top_down.agents import (
    AnalystAgent,
    CharacterDesignerAgent,
    CriticAgent,
    EditorAgent,
    PlotArchitectAgent,
    WorldBuilderAgent,
    WriterAgent,
)
from asg_top_down.schemas import (
    CharactersArtifact,
    OutlineArtifact,
    ReviewArtifact,
    StoryRequest,
    WorldArtifact,
)

from fakes import FakeProvider, RESPONSES


def test_each_agent_returns_its_contract() -> None:
    provider = FakeProvider()
    request = AnalystAgent(provider).run("Una historia")
    world = WorldBuilderAgent(provider).run(request)
    characters = CharacterDesignerAgent(provider).run(request, world)
    outline = PlotArchitectAgent(provider).run(request, world, characters)
    draft = WriterAgent(provider).run(request, world, characters, outline)
    review = CriticAgent(provider).run(request, outline, draft)
    story = EditorAgent(provider).run(request, outline, draft, review)

    assert isinstance(request, StoryRequest)
    assert isinstance(world, WorldArtifact)
    assert isinstance(characters, CharactersArtifact)
    assert isinstance(outline, OutlineArtifact)
    assert isinstance(review, ReviewArtifact)
    assert draft == "# Borrador"
    assert story.startswith("# Historia final")


def test_analyst_default_contract_is_spanish_and_1500_words() -> None:
    request = RESPONSES[StoryRequest]
    assert request.language == "español"
    assert request.target_words == 1500

