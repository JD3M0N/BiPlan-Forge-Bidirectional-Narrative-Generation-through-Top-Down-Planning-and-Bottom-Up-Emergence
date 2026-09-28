"""Shared test doubles implementing the full StoryGeneratorAdapter contract."""

from __future__ import annotations

from pathlib import Path

from asg_telegram.contract import (
    BriefSpec,
    GenerationCancelled,
    GenerationEvent,
    GenerationFailure,
    GenerationProgress,
    OptionChoice,
    OptionSpec,
    RunSummary,
    StoryOutline,
)

FORMAT_SPEC = OptionSpec(
    "format",
    "choice",
    "Formato de salida",
    "Qué entrega la función terminada.",
    (
        OptionChoice("narrative", "Historia narrativa", "Prosa a partir del plan."),
        OptionChoice("script-native", "Guion teatral", "Escrito por escenas."),
        OptionChoice("simulated", "Historia simulada", "Actuada por los personajes.", note="Caro."),
    ),
)
PROFILE_SPEC = OptionSpec(
    "narrative_profile",
    "choice",
    "Perfil narrativo",
    "La escala de la historia.",
    (
        OptionChoice(None, "Automático", "Lo deduce el analista."),
        OptionChoice("essential", "Esencial"),
        OptionChoice("developed", "Desarrollada"),
        OptionChoice("expansive", "Expansiva"),
    ),
)
LEDGER_SPEC = OptionSpec("promise_ledger", "toggle", "Ledger de promesas", "Traza promesas.")
VOICE_SPEC = OptionSpec(
    "narrative_voice",
    "choice",
    "Visión",
    "Desde dónde se cuenta.",
    (
        OptionChoice("omniscient", "Omnisciente"),
        OptionChoice("first_person", "Primera persona"),
    ),
    formats=frozenset({"simulated"}),
)
NARRATOR_SPEC = OptionSpec(
    "narrator",
    "text",
    "Personaje de la visión",
    "Quién cuenta la historia.",
    max_length=80,
    formats=frozenset({"simulated"}),
    requires=(("narrative_voice", ("first_person",)),),
)
TURNS_SPEC = OptionSpec(
    "turns_per_beat",
    "integer",
    "Turnos por beat",
    "Cuántos turnos dura un beat.",
    minimum=2,
    maximum=16,
    formats=frozenset({"simulated"}),
)
AUDIO_SPEC = OptionSpec("audio", "toggle", "Narración en audio", "Lee la historia en audio.")
AUDIO_VOICE_SPEC = OptionSpec(
    "audio_voice",
    "choice",
    "Voz del audio",
    "Quién lee la historia.",
    (
        OptionChoice("", "Automática"),
        OptionChoice("es-MX-DaliaNeural", "Dalia · mujer", group="México"),
        OptionChoice("es-ES-AlvaroNeural", "Álvaro · hombre", group="España"),
    ),
    requires=(("audio", (True,)),),
    previewable=True,
)

OPTION_SPECS = (
    FORMAT_SPEC,
    PROFILE_SPEC,
    LEDGER_SPEC,
    VOICE_SPEC,
    NARRATOR_SPEC,
    TURNS_SPEC,
    AUDIO_SPEC,
    AUDIO_VOICE_SPEC,
)

BRIEF_SPEC = BriefSpec(
    limits={
        "title": 120,
        "genre": 80,
        "setting": 400,
        "plot": 4000,
        "notes": 1500,
        "name": 80,
        "description": 600,
        "secret": 400,
    },
    max_cast=10,
    roles=(
        OptionChoice("", "Sin rol"),
        OptionChoice("protagonista", "Protagonista"),
        OptionChoice("antagonista", "Antagonista"),
    ),
    pronouns=(
        OptionChoice("", "—"),
        OptionChoice("ella", "ella"),
        OptionChoice("él", "él"),
    ),
)

DEFAULT_OPTIONS = {
    "format": "narrative",
    "narrative_profile": None,
    "promise_ledger": True,
    "narrative_voice": "omniscient",
    "narrator": "",
    "turns_per_beat": 8,
    "audio": True,
    "audio_voice": "",
}


class FakeGenerator:
    """A generator double that fully honours StoryGeneratorAdapter."""

    display_name = "Fake"
    option_specs = OPTION_SPECS
    brief_spec = BRIEF_SPEC

    def __init__(self, story_directory: Path):
        self.story_directory = story_directory
        self.calls: list[dict] = []
        self.prompts: list = []

    def default_options(self) -> dict:
        return dict(DEFAULT_OPTIONS)

    def normalize_options(self, values):
        chosen = {k: v for k, v in values.items() if k in DEFAULT_OPTIONS}
        merged = {**self.default_options(), **chosen}
        spec = next(s for s in self.option_specs if s.key == "format")
        if merged["format"] not in {c.value for c in spec.choices}:
            raise ValueError("Formato de salida desconocido.")
        if merged.get("turns_per_beat") is not None and merged["turns_per_beat"] < 2:
            raise ValueError("turns_per_beat: debe ser mayor o igual que 2.")
        if merged.get("narrative_voice") != "first_person":
            merged["narrator"] = ""
        return merged

    def validate_outline(self, outline: StoryOutline) -> None:
        if not outline.plot.strip():
            raise ValueError("La trama no puede estar vacía.")
        names = [member.name.strip().casefold() for member in outline.cast]
        if len(names) != len(set(names)):
            raise ValueError("El reparto repite un nombre.")

    def startup_details(self):
        return (("Generador", "Fake"),)

    def generate(
        self,
        request,
        *,
        options=None,
        on_progress=None,
        on_run_created=None,
        on_event=None,
        should_cancel=None,
    ) -> Path:
        self.prompts.append(request)
        self.calls.append({"request": request, "options": dict(options or {})})
        self._report(on_progress, on_event, should_cancel)
        if on_run_created is not None:
            on_run_created(self.story_directory)
        return self.story_directory

    def _report(self, on_progress, on_event, should_cancel):
        """Emit whatever progress and events this double is configured with."""

    def summarize(self, run_dir: Path) -> RunSummary:
        from asg_telegram.generators import summarize_run

        return summarize_run(run_dir)


class FailingGenerator(FakeGenerator):
    def __init__(self):
        super().__init__(Path("."))

    def generate(self, request, **kwargs):
        raise GenerationFailure(
            "No se pudo completar el capítulo 1 «El eco».",
            code="ARTIFACT_VALIDATION_FAILED",
            stage="planning",
            recommendation="Revisa los checkpoints de planificación.",
            run_id="run-seguro",
        )


class CancellingGenerator(FakeGenerator):
    """A generator whose should_cancel is asserted True at some point."""

    def generate(self, request, *, on_progress=None, should_cancel=None, **kwargs):
        on_progress(GenerationProgress(10, "analysis", "Analizando"))
        if should_cancel and should_cancel():
            raise GenerationCancelled("analysis")
        on_progress(GenerationProgress(20, "world", "Construyendo el mundo"))
        if should_cancel and should_cancel():
            raise GenerationCancelled("world")
        raise AssertionError("la generación debió detenerse")


class BrokenGenerator(FakeGenerator):
    def generate(self, request, **kwargs):
        raise RuntimeError("el proveedor devolvió basura")


__all__ = [
    "AUDIO_SPEC",
    "AUDIO_VOICE_SPEC",
    "BRIEF_SPEC",
    "BrokenGenerator",
    "CancellingGenerator",
    "DEFAULT_OPTIONS",
    "FORMAT_SPEC",
    "FailingGenerator",
    "FakeGenerator",
    "GenerationEvent",
    "LEDGER_SPEC",
    "NARRATOR_SPEC",
    "OPTION_SPECS",
    "PROFILE_SPEC",
    "TURNS_SPEC",
    "VOICE_SPEC",
]
