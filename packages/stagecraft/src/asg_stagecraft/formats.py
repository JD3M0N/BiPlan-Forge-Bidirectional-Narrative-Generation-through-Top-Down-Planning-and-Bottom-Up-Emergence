"""Output format, script method, narrative voice and actor memory selection.

Shared by every entry point: the CLI, the console, the Telegram bot and the public facade all
present the same options, so a run generated from one surface is reproducible from another.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StoryFormat(StrEnum):
    """The shape of the final artifact a run delivers."""

    NARRATIVE = "narrative"
    SCRIPT = "script"
    SIMULATED = "simulated"


class ScriptMethod(StrEnum):
    """How a script run turns the plan into scenes, ignored for narrative runs."""

    NATIVE = "native"
    ADAPTED = "adapted"


class NarrativeVoice(StrEnum):
    """Which point of view narrates a simulated run's prose from the performance log.

    The voice decides what the narrator is allowed to see, not only how it writes: each one
    carries a deterministic filter over the log (see stage/voices.py). Adding a point of view
    is adding a strategy there, never a branch in the narrator's prompt.
    """

    OMNISCIENT = "omniscient"
    FOCALIZED = "focalized"
    FIRST_PERSON = "first_person"
    # Third person held to one character: the first-person filter, told as "she", not "I" (7.3).
    LIMITED = "limited"


class ActorMemory(StrEnum):
    """Whether each actor remembers only what it witnessed, or everything public.

    ``own`` is the thesis claim: a character acts on partial knowledge. ``shared`` is its
    control arm, which keeps every other moving part identical so the difference between two
    corpora is attributable to the memory model alone.
    """

    OWN = "own"
    SHARED = "shared"


class SimulationMode(StrEnum):
    """Whether a performed beat must be reached or may change the remaining play."""

    FIXED = "fixed"
    ADAPTIVE = "adaptive"


@dataclass(frozen=True)
class OutputChoice:
    """One combined output option, as shown on every interactive surface."""

    key: str
    label: str
    story_format: StoryFormat
    script_method: ScriptMethod
    description: str = ""


# Labels an interface uses for the control that sets story_format and script_method together.
OUTPUT_LABEL = "Formato de salida"
OUTPUT_HELP = "Qué entrega la función terminada."

OUTPUT_CHOICES: tuple[OutputChoice, ...] = (
    OutputChoice(
        "narrative",
        "Historia narrativa",
        StoryFormat.NARRATIVE,
        ScriptMethod.NATIVE,
        "Prosa escrita a partir del plan: el enfoque Top-Down.",
    ),
    OutputChoice(
        "script-native",
        "Guion teatral · escrito por escenas",
        StoryFormat.SCRIPT,
        ScriptMethod.NATIVE,
        "El plan escrito directamente como obra de teatro, por escenas.",
    ),
    OutputChoice(
        "script-adapted",
        "Guion teatral · adaptado de la prosa",
        StoryFormat.SCRIPT,
        ScriptMethod.ADAPTED,
        "La prosa terminada, adaptada después a guion.",
    ),
    # A simulated run always stages the native script: adapting prose into a script only to
    # perform it and narrate prose again would run the same material through the model twice
    # for no gain, so the method axis is fixed here rather than offered.
    OutputChoice(
        "simulated",
        "Historia simulada · los personajes actúan el guion",
        StoryFormat.SIMULATED,
        ScriptMethod.NATIVE,
        "Los personajes representan el guion con memoria propia y se narra la función.",
    ),
)

# What each run costs, as the roadmap's measurement protocol states it; shown before a launch.
FORMAT_COST_HINTS: dict[StoryFormat, str] = {
    StoryFormat.NARRATIVE: "Una narrativa cuesta unas 16 llamadas al modelo.",
    StoryFormat.SCRIPT: "Un guion cuesta unas 20 llamadas al modelo.",
    StoryFormat.SIMULATED: (
        "Una simulada cuesta entre 98 y 126 llamadas: una parte grande del cupo diario."
    ),
}


def output_choice(story_format: StoryFormat, script_method: ScriptMethod) -> OutputChoice:
    """Return the combined choice matching one format and method pair."""
    if story_format is StoryFormat.NARRATIVE:
        return OUTPUT_CHOICES[0]
    if story_format is StoryFormat.SIMULATED:
        return OUTPUT_CHOICES[-1]
    for choice in OUTPUT_CHOICES:
        if choice.story_format is story_format and choice.script_method is script_method:
            return choice
    raise ValueError(f"no combined choice for {story_format.value}/{script_method.value}")


def output_choice_for(key: str) -> OutputChoice:
    """Look up one combined choice by its stable key, or reject an unknown one."""
    for choice in OUTPUT_CHOICES:
        if choice.key == key:
            return choice
    allowed = ", ".join(item.key for item in OUTPUT_CHOICES)
    raise ValueError(f"unknown output choice {key!r}; allowed values: {allowed}")


@dataclass(frozen=True)
class VoiceChoice:
    """One point of view as every surface presents it.

    takes_character says the voice is told from one character the caller may name; the stage
    strategy for the voice agrees with it, and a test holds the two together.
    """

    voice: NarrativeVoice
    label: str
    description: str
    takes_character: bool


VOICE_CHOICES: tuple[VoiceChoice, ...] = (
    VoiceChoice(
        NarrativeVoice.OMNISCIENT,
        "Tercera persona omnisciente",
        "El narrador entra en la cabeza de todos: cuenta cada turno y cada pensamiento.",
        False,
    ),
    VoiceChoice(
        NarrativeVoice.FOCALIZED,
        "Tercera persona focalizada por escena",
        "Todo lo público y la vida interior de un personaje por escena: el que más actúa en ella.",
        False,
    ),
    VoiceChoice(
        NarrativeVoice.LIMITED,
        "Tercera persona limitada a un personaje",
        "Solo lo que ese personaje presenció, y solo sus pensamientos, contado en tercera persona.",
        True,
    ),
    VoiceChoice(
        NarrativeVoice.FIRST_PERSON,
        "Primera persona de un personaje",
        "Ese personaje cuenta lo que vivió: solo lo que presenció y lo que pensó.",
        True,
    ),
)


def voice_choice(voice: NarrativeVoice) -> VoiceChoice:
    """Return how a point of view is presented, for any voice the pipeline knows."""
    for choice in VOICE_CHOICES:
        if choice.voice is voice:
            return choice
    raise ValueError(f"no presentation for voice {voice.value!r}")


@dataclass(frozen=True)
class MemoryChoice:
    """One actor memory model as every surface presents it."""

    memory: ActorMemory
    label: str
    description: str


MEMORY_CHOICES: tuple[MemoryChoice, ...] = (
    MemoryChoice(
        ActorMemory.OWN,
        "Memoria propia",
        "Cada personaje recuerda solo lo que presenció. Es la afirmación de la tesis.",
    ),
    MemoryChoice(
        ActorMemory.SHARED,
        "Memoria compartida",
        "Todo lo público llega a todo el reparto. Es el brazo de control de la ablación.",
    ),
)
