from .base import Agent, json_text
from ..schemas import StoryPlanArtifact, StoryRequest, WorldArtifact


class WorldBuilderAgent(Agent[WorldArtifact]):
    name = "world"

    def run(self, request: StoryRequest, plan: StoryPlanArtifact) -> WorldArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Eres diseñador de mundos. Define reglas, lugares y una atmósfera "
                "consistentes que sostengan el plan y afecten de forma concreta el conflicto, "
                "las decisiones o la causalidad. Evita detalles decorativos sin consecuencias "
                "narrativas."
            ),
            prompt=f"REQUISITOS:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}",
            schema=WorldArtifact,
        )
