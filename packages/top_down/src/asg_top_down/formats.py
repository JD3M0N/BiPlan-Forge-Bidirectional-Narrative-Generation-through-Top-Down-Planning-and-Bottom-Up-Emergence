"""Output format and script method selection, shared by every entry point."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StoryFormat(StrEnum):
    """The shape of the final artifact a run delivers."""

    NARRATIVE = "narrative"
    SCRIPT = "script"


class ScriptMethod(StrEnum):
    """How a script run turns the plan into scenes, ignored for narrative runs."""

    NATIVE = "native"
    ADAPTED = "adapted"


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
)


def output_choice(story_format: StoryFormat, script_method: ScriptMethod) -> OutputChoice:
    """Return the combined choice matching one format and method pair."""
    if story_format is StoryFormat.NARRATIVE:
        return OUTPUT_CHOICES[0]
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
