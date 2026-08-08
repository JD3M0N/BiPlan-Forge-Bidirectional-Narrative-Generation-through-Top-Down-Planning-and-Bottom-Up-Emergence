from collections import Counter

from pydantic import BaseModel

from asg_top_down.schemas import (
    ArchetypeSelection, CausalEdge, Character, CharactersArtifact,
    DirectedStoryArtifact, ReviewArtifact, Scene, StoryBeat, StoryPlanArtifact,
    StoryRequest, WorldArtifact,
)

RESPONSES: dict[type[BaseModel], BaseModel] = {
    StoryRequest: StoryRequest(original_prompt="Una historia", title="La señal", genre="ciencia ficción", tone="melancólico", premise="Una señal cambia una vida."),
    StoryPlanArtifact: StoryPlanArtifact(logline="Ada descifra una señal.", theme="Confianza", central_conflict="Verdad contra incredulidad", progression=["Descubre", "Pierde", "Comprende"], intended_ending="Comparte el mensaje.", archetypes=ArchetypeSelection(primary="discovery", secondary=["mystery"], confidence=.9, prompt_evidence=["señal"], rationale="La verdad transforma a Ada.")),
    WorldArtifact: WorldArtifact(setting="Una estación orbital", time_period="Futuro", rules=["La comunicación tarda"], locations=["Observatorio"], atmosphere="Decadente"),
    CharactersArtifact: CharactersArtifact(characters=[Character(name="Ada", narrative_role="protagonista", jungian_archetype="explorer", goal="Descifrar", motivation="Comprender", conflict="Nadie le cree", arc="Aprende a confiar")]),
    DirectedStoryArtifact: DirectedStoryArtifact(
        scenes=[
            Scene(id="scene_1", order=1, title="Señal", purpose="Descubrir", point_of_view="Ada", location="Observatorio", characters=["Ada"], target_words=700, entry_state="Rutina", exit_state="Alarma", beat_ids=["beat_1", "beat_2"]),
            Scene(id="scene_2", order=2, title="Respuesta", purpose="Resolver", point_of_view="Ada", location="Observatorio", characters=["Ada"], target_words=800, entry_state="Alarma", exit_state="Esperanza", beat_ids=["beat_3"]),
        ],
        beats=[
            StoryBeat(id="beat_1", scene_id="scene_1", global_order=1, local_order=1, beat_type="setup", objective="Observar", conflict="Ruido", action="Ada detecta la señal", outcome="Guarda datos", participants=["Ada"], emotional_shift="curiosidad"),
            StoryBeat(id="beat_2", scene_id="scene_1", global_order=2, local_order=2, beat_type="turn", objective="Verificar", conflict="La señal cesa", action="Ada pierde la señal", outcome="Busca una pauta", participants=["Ada"], emotional_shift="temor"),
            StoryBeat(id="beat_3", scene_id="scene_2", global_order=3, local_order=1, beat_type="resolution", objective="Comprender", conflict="Duda", action="Ada descifra el patrón", outcome="Comparte el mensaje", participants=["Ada"], emotional_shift="esperanza"),
        ],
        candidate_edges=[
            CausalEdge(source="beat_1", target="beat_2", relation="causes", strength=5, rationale="La detección permite verificar."),
            CausalEdge(source="beat_2", target="beat_3", relation="motivates", strength=4, rationale="La pérdida impulsa la búsqueda."),
        ],
    ),
    ReviewArtifact: ReviewArtifact(coherence_score=8, continuity_score=8, style_score=7, compliance_score=9, archetype_score=8, graph_coverage_score=9, strengths=["Clara"], issues=["Final breve"], revision_instructions=["Desarrollar final"]),
}


class FakeProvider:
    model_name = "fake-flash"

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.text_calls = Counter()
        self.fail_on = fail_on

    def generate_structured(self, *, system_instruction: str, prompt: str, schema: type[BaseModel]) -> BaseModel:
        self.calls.append(("structured", schema.__name__))
        if self.fail_on == schema.__name__:
            raise RuntimeError("fallo simulado")
        return RESPONSES[schema].model_copy(deep=True)

    def generate_text(self, *, system_instruction: str, prompt: str) -> str:
        kind = "story" if "editor literario" in system_instruction else "scene"
        self.calls.append(("text", kind))
        self.text_calls[kind] += 1
        if self.fail_on == kind:
            raise RuntimeError("fallo simulado")
        return "# Historia final\n\nTexto revisado." if kind == "story" else f"## Escena {self.text_calls[kind]}\n\nTexto."
