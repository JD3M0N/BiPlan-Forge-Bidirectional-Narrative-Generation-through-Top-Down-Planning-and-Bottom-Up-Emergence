from .base import Agent, json_text
from ..schemas import StoryPlanArtifact, StoryRequest, WorldArtifact


class WorldBuilderAgent(Agent[WorldArtifact]):
    name = "world"

    def run(self, request: StoryRequest, plan: StoryPlanArtifact) -> WorldArtifact:
        return self.provider.generate_structured(
            system_instruction="Eres diseñador de mundos. Define elementos que sostengan el plan, el tono y el conflicto, con reglas consistentes.",
            prompt=f"REQUISITOS:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}",
            schema=WorldArtifact,
        )
