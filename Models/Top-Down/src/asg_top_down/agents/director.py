from .base import Agent, json_text
from ..schemas import CharactersArtifact, DirectedStoryArtifact, StoryPlanArtifact, StoryRequest, WorldArtifact
from ..taxonomies import NarrativeArchetype


class DirectorAgent(Agent[DirectedStoryArtifact]):
    name = "director"

    def run(
        self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact,
        characters: CharactersArtifact, archetypes: list[NarrativeArchetype],
        diagnostics: list[str] | None = None, attempt: int = 1,
    ) -> DirectedStoryArtifact:
        taxonomy = [item.model_dump(mode="json") for item in archetypes]
        return self.provider.generate_structured(
            system_instruction=(
                "Eres Director narrativo y planificador STORYTELLER. Genera capítulos y nodos "
                "SVO CBN/CPN/CEN. Cada capítulo empieza con exactamente un CBN, contiene CPN "
                "dinámicos y termina con un CEN. Cada CPN debe avanzar hacia el CEN y cumplir "
                "goals derivados literalmente de common_beats o suggested_progression. Reparte "
                "exactamente target_words entre capítulos y nodos. Crea dependencias hacia "
                "adelante que conecten cada CBN con su CEN y el CEN con el próximo CBN; jamás "
                "crees ciclos. Los órdenes son contiguos desde 1 y timestamps desde 0. "
                "Cubre en orden exposition, rising_action, climax, falling_action y denouement. "
                "Si recibes diagnósticos, replantea el conjunto completo: elimina, sustituye o "
                "añade CPN según sea necesario, sin repetir la versión fallida."
            ),
            prompt=(
                f"INTENTO: {attempt}/5\nDIAGNÓSTICOS PREVIOS:\n{diagnostics or ['ninguno']}\n\n"
                f"REQUISITOS:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}\n\n"
                f"MUNDO:\n{json_text(world)}\n\nPERSONAJES:\n{json_text(characters)}\n\n"
                f"TAXONOMÍAS:\n{taxonomy}"
            ),
            schema=DirectedStoryArtifact,
        )
