from .base import Agent, json_text
from ..schemas import NarrativeGraphArtifact, ReviewArtifact, StoryPlanArtifact, StoryRequest


class EditorAgent(Agent[str]):
    name = "story"

    def run(self, request: StoryRequest, plan: StoryPlanArtifact, graph: NarrativeGraphArtifact, draft: str, review: ReviewArtifact) -> str:
        return self.provider.generate_text(
            system_instruction=(
                "Eres editor literario. Reescribe una sola vez el borrador aplicando la crítica. "
                "No cambies hechos, dependencias ni resultados establecidos por el DAG. Devuelve "
                "únicamente la historia final completa en Markdown."
            ),
            prompt=(f"REQUISITOS:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}\n\nGRAFO:\n{json_text(graph)}"
                    f"\n\nCRÍTICA:\n{json_text(review)}\n\nBORRADOR:\n{draft}"),
        )
