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


class ActorMemory(StrEnum):
    """Whether each actor remembers only what it witnessed, or everything public.

    ``own`` is the thesis claim: a character acts on partial knowledge. ``shared`` is its
    control arm, which keeps every other moving part identical so the difference between two
    corpora is attributable to the memory model alone.
    """

    OWN = "own"
    SHARED = "shared"


@dataclass(frozen=True)
class OutputChoice:
    """One combined output option, as shown on every interactive surface."""

    key: str
    label: str
    story_format: StoryFormat
    script_method: ScriptMethod


OUTPUT_CHOICES: tuple[OutputChoice, ...] = (
    OutputChoice("narrative", "Historia narrativa", StoryFormat.NARRATIVE, ScriptMethod.NATIVE),
    OutputChoice(
        "script-native",
        "Guion teatral · escrito por escenas",
        StoryFormat.SCRIPT,
        ScriptMethod.NATIVE,
    ),
    OutputChoice(
        "script-adapted",
        "Guion teatral · adaptado de la prosa",
        StoryFormat.SCRIPT,
        ScriptMethod.ADAPTED,
    ),
    # A simulated run always stages the native script: adapting prose into a script only to
    # perform it and narrate prose again would run the same material through the model twice
    # for no gain, so the method axis is fixed here rather than offered.
    OutputChoice(
        "simulated",
        "Historia simulada · los personajes actúan el guion",
        StoryFormat.SIMULATED,
        ScriptMethod.NATIVE,
    ),
)


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
