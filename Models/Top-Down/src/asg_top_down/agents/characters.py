from .base import Agent, json_text
from ..schemas import CharactersArtifact, StoryPlanArtifact, StoryRequest, WorldArtifact
from ..taxonomies import TaxonomyRepository


class CharacterDesignerAgent(Agent[CharactersArtifact]):
    name = "characters"

    def __init__(self, provider, taxonomies: TaxonomyRepository) -> None:
        super().__init__(provider)
        self.taxonomies = taxonomies

    def run(self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact) -> CharactersArtifact:
        result = self.provider.generate_structured(
            system_instruction=(
                "Eres diseñador de personajes. Crea un reparto compacto y asigna a cada "
                "personaje un jungian_archetype usando únicamente un ID del catálogo. "
                "Distingue ese arquetipo de su función narrativa."
            ),
            prompt=(f"REQUISITOS:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}"
                    f"\n\nMUNDO:\n{json_text(world)}\n\nROLES:\n{json_text(self.taxonomies.roles)}"),
            schema=CharactersArtifact,
        )
        self.taxonomies.validate_role_ids([c.jungian_archetype for c in result.characters])
        return result
