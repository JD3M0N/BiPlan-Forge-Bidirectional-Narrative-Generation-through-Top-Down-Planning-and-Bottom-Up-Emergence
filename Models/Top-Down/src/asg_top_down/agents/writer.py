from .base import Agent, json_text
from ..schemas import (
    ChapterComplianceArtifact, ChapterPlan, CharactersArtifact,
    StoryPlanArtifact, StoryRequest, StorylineArtifact, WorldArtifact,
)


class SceneWriterAgent(Agent[str]):
    """Compatibility name; writes one STORYTELLER chapter text block."""
    name = "chapters"

    def run(self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact,
            characters: CharactersArtifact, graph: StorylineArtifact,
            chapter: ChapterPlan, prior_summary: str, revision: str = "") -> str:
        nodes = [x for x in graph.nodes if x.chapter_id == chapter.id]
        dependencies = [x for x in graph.accepted_edges if x.source in {n.id for n in nodes} or x.target in {n.id for n in nodes}]
        return self.provider.generate_text(
            system_instruction=(
                "Eres escritor de ficción. Redacta únicamente el capítulo solicitado en Markdown. "
                "Realiza explícitamente todos los nodos en orden topológico, sus goals taxonómicos "
                "y fases dramáticas sin mencionar el proceso. Respeta el presupuesto de palabras "
                "y no contradigas el texto previo ni el NEKG."
            ),
            prompt=(f"REQUISITOS:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}\n\nMUNDO:\n{json_text(world)}"
                    f"\n\nPERSONAJES:\n{json_text(characters)}\n\nCAPÍTULO:\n{json_text(chapter)}"
                    f"\n\nNODOS:\n{json_text(nodes)}\n\nDEPENDENCIAS:\n{json_text(dependencies)}"
                    f"\n\nCONTEXTO PREVIO:\n{prior_summary or 'Primer capítulo.'}"
                    f"\n\nCORRECCIÓN SOLICITADA:\n{revision or 'ninguna'}"),
        )


class ChapterComplianceAgent(Agent[ChapterComplianceArtifact]):
    name = "chapter_compliance"

    def run(self, chapter: ChapterPlan, graph: StorylineArtifact, text: str) -> ChapterComplianceArtifact:
        nodes = [x for x in graph.nodes if x.chapter_id == chapter.id]
        return self.provider.generate_structured(
            system_instruction=(
                "Audita un capítulo. passed solo puede ser true cuando se realizan todos los nodos "
                "SVO, todos sus goals y el conteo está dentro de ±10% del target. Cuenta palabras "
                "separadas por espacios y devuelve instrucciones concretas si falla."
            ),
            prompt=f"CAPÍTULO:\n{json_text(chapter)}\n\nNODOS:\n{json_text(nodes)}\n\nTEXTO:\n{text}",
            schema=ChapterComplianceArtifact,
        )
