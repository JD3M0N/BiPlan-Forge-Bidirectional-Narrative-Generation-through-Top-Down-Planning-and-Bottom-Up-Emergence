from .base import Agent, json_text
from ..schemas import NarrativeGraphArtifact, ReviewArtifact, StoryPlanArtifact, StoryRequest


class CriticAgent(Agent[ReviewArtifact]):
    name = "review"

    def run(self, request: StoryRequest, plan: StoryPlanArtifact, graph: NarrativeGraphArtifact, draft: str) -> ReviewArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Eres crítico editorial. Evalúa coherencia, continuidad, estilo, cumplimiento, "
                "realización de los arquetipos y cobertura de todos los beats y relaciones del DAG."
            ),
            prompt=f"REQUISITOS:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}\n\nGRAFO:\n{json_text(graph)}\n\nBORRADOR:\n{draft}",
            schema=ReviewArtifact,
        )
