from .base import Agent, json_text
from ..schemas import CharactersArtifact, DirectedStoryArtifact, StoryPlanArtifact, StoryRequest, WorldArtifact


class DirectorAgent(Agent[DirectedStoryArtifact]):
    name = "director"

    def run(self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact, characters: CharactersArtifact) -> DirectedStoryArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Eres Director narrativo. Divide la historia en varias escenas ordenadas y "
                "cada escena en uno o más beats atómicos. Los IDs deben ser estables y aptos "
                "para Mermaid (solo letras, números y guiones bajos). Distribuye target_words "
                "aproximadamente hasta el total pedido. Crea relaciones causales dirigidas con "
                "fuerza 1-5; no uses relaciones meramente temporales."
            ),
            prompt=(f"REQUISITOS:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}"
                    f"\n\nMUNDO:\n{json_text(world)}\n\nPERSONAJES:\n{json_text(characters)}"),
            schema=DirectedStoryArtifact,
        )
