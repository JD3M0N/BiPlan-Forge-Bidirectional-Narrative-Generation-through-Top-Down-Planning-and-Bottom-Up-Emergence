from collections import Counter

from pydantic import BaseModel

from asg_top_down.schemas import (
    Character,
    CharactersArtifact,
    OutlineArtifact,
    PlotBeat,
    ReviewArtifact,
    StoryRequest,
    WorldArtifact,
)


RESPONSES: dict[type[BaseModel], BaseModel] = {
    StoryRequest: StoryRequest(
        original_prompt="Una historia de prueba",
        title="La señal",
        language="español",
        genre="ciencia ficción",
        tone="melancólico",
        target_words=1500,
        premise="Una señal imposible cambia una vida.",
    ),
    WorldArtifact: WorldArtifact(
        setting="Una estación orbital",
        time_period="Futuro lejano",
        rules=["La comunicación tiene retraso"],
        locations=["Observatorio"],
        atmosphere="Decadente",
    ),
    CharactersArtifact: CharactersArtifact(
        characters=[
            Character(
                name="Ada",
                role="protagonista",
                goal="Descifrar la señal",
                motivation="Comprender el cielo",
                conflict="Nadie le cree",
                arc="Aprende a confiar",
            )
        ],
        relationships=[],
    ),
    OutlineArtifact: OutlineArtifact(
        logline="Ada descifra una señal.",
        central_conflict="Verdad contra incredulidad",
        theme="Confianza",
        beats=[
            PlotBeat(
                order=1,
                name="Inicio",
                purpose="Presentar",
                events=["Aparece la señal"],
                characters=["Ada"],
            ),
            PlotBeat(
                order=2,
                name="Crisis",
                purpose="Confrontar",
                events=["La señal se apaga"],
                characters=["Ada"],
            ),
            PlotBeat(
                order=3,
                name="Final",
                purpose="Resolver",
                events=["Ada comprende"],
                characters=["Ada"],
            ),
        ],
        ending="Ada comparte el mensaje.",
    ),
    ReviewArtifact: ReviewArtifact(
        coherence_score=8,
        continuity_score=8,
        style_score=7,
        compliance_score=9,
        strengths=["Estructura clara"],
        issues=["Final apresurado"],
        revision_instructions=["Desarrollar el final"],
    ),
}


class FakeProvider:
    model_name = "fake-flash"

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.text_calls = Counter()
        self.fail_on = fail_on

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[BaseModel]
    ) -> BaseModel:
        self.calls.append(("structured", schema.__name__))
        if self.fail_on == schema.__name__:
            raise RuntimeError("fallo simulado")
        return RESPONSES[schema].model_copy(deep=True)

    def generate_text(self, *, system_instruction: str, prompt: str) -> str:
        kind = "story" if "editor literario" in system_instruction else "draft"
        self.calls.append(("text", kind))
        self.text_calls[kind] += 1
        if self.fail_on == kind:
            raise RuntimeError("fallo simulado")
        return "# Historia final\n\nTexto revisado." if kind == "story" else "# Borrador"

