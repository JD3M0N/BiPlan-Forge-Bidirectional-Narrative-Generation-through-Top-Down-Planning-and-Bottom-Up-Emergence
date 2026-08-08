from .base import Agent, json_text
from ..schemas import CharactersArtifact, NarrativeGraphArtifact, Scene, StoryPlanArtifact, StoryRequest, WorldArtifact


class SceneWriterAgent(Agent[str]):
    name = "scenes"

    def run(self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact, characters: CharactersArtifact, graph: NarrativeGraphArtifact, scene: Scene, prior_summary: str) -> str:
        beats = [beat for beat in graph.beats if beat.id in scene.beat_ids]
        dependencies = [edge for edge in graph.accepted_edges if edge.target in scene.beat_ids]
        return self.provider.generate_text(
            system_instruction=(
                "Eres escritor de ficción. Redacta únicamente la escena solicitada en Markdown, "
                "sin notas del proceso. Respeta sus beats, estado de entrada/salida, punto de "
                "vista, idioma y presupuesto aproximado. No contradigas el contexto previo."
            ),
            prompt=(f"REQUISITOS:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}\n\nMUNDO:\n{json_text(world)}"
                    f"\n\nPERSONAJES:\n{json_text(characters)}\n\nESCENA:\n{json_text(scene)}"
                    f"\n\nBEATS:\n{json_text(beats)}\n\nDEPENDENCIAS:\n{json_text(dependencies)}"
                    f"\n\nCONTEXTO PREVIO:\n{prior_summary or 'Esta es la primera escena.'}"),
        )
