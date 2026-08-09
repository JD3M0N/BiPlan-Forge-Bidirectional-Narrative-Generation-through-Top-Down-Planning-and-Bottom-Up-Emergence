from .base import Agent, json_text
from ..schemas import FreytagReviewArtifact, StorylineArtifact


class DramaAgent(Agent[FreytagReviewArtifact]):
    name = "drama"

    def run(self, storyline: StorylineArtifact, text: str | None = None) -> FreytagReviewArtifact:
        mode = "texto final y su grafo" if text is not None else "grafo narrativo"
        return self.provider.generate_structured(
            system_instruction=(
                f"Eres agente de drama. Evalúa el {mode} según Freytag. Deben existir, en este "
                "orden global: exposition, rising_action, climax, falling_action y denouement. "
                "Asocia evidencia a capítulos y nodos. passed solo es true si las cinco fases "
                "están presentes, ordenadas y el clímax es dramáticamente suficiente."
            ),
            prompt=f"STORYLINE:\n{json_text(storyline)}\n\nTEXTO:\n{text or 'Aún no escrito.'}",
            schema=FreytagReviewArtifact,
        )
