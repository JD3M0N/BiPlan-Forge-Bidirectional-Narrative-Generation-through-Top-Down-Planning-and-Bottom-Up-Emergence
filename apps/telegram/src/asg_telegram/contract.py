"""Application-owned contract every story generator adapter must satisfy.

The bot speaks only these types. Keeping them here, instead of importing the
Stagecraft pipeline types directly, means a second approach can be plugged in
without touching conversation, delivery or console code.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

OptionValue = str | int | bool | None
OptionKind = Literal["choice", "toggle", "integer", "text"]


@dataclass(frozen=True, slots=True)
class GenerationProgress:
    """One generation milestone expressed as a percentage and a description."""

    percent: int
    stage: str
    description: str

    def __post_init__(self) -> None:
        """Reject percentages outside the range a progress bar can render."""
        if not 0 <= self.percent <= 100:
            raise ValueError("percent must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class GenerationEvent:
    """One structured diagnostic event destined for the operator console."""

    message: str
    stage: str | None = None
    kind: str | None = None


@dataclass(frozen=True, slots=True)
class OptionChoice:
    """One selectable value of an OptionSpec."""

    value: OptionValue
    label: str
    description: str = ""
    group: str = ""
    note: str = ""


@dataclass(frozen=True, slots=True)
class OptionSpec:
    """One configurable run option, as the chat panel presents it."""

    key: str
    kind: OptionKind
    label: str
    help: str = ""
    choices: tuple[OptionChoice, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    max_length: int | None = None
    # Which output formats this option applies to; empty means every format.
    formats: frozenset[str] = frozenset()
    # ((key, allowed_values), ...): every condition must hold for the option to be offered.
    requires: tuple[tuple[str, tuple[OptionValue, ...]], ...] = ()
    previewable: bool = False

    def applies(self, values: Mapping[str, OptionValue]) -> bool:
        """Report whether this option is offered for the current run values."""
        if self.formats and values.get("format") not in self.formats:
            return False
        return all(values.get(key) in allowed for key, allowed in self.requires)

    def choice_for(self, value: OptionValue) -> OptionChoice | None:
        """Return the offered choice matching a value, or None for an unknown one."""
        return next((choice for choice in self.choices if choice.value == value), None)


@dataclass(frozen=True, slots=True)
class CastEntry:
    """One cast member declared through the guided wizard."""

    name: str
    role: str = ""
    pronoun: str = ""
    description: str = ""
    secret: str = ""


@dataclass(frozen=True, slots=True)
class StoryOutline:
    """A story described as a structured brief, mirroring asg_stagecraft.StoryBrief."""

    plot: str
    title: str = ""
    genre: str = ""
    setting: str = ""
    cast: tuple[CastEntry, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict:
        """Convert this outline into the plain dict a StoryBrief validates from."""
        return {
            "plot": self.plot,
            "title": self.title,
            "genre": self.genre,
            "setting": self.setting,
            "cast": [vars(member) for member in self.cast],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping) -> StoryOutline:
        """Rebuild an outline from the dict its to_dict produced."""
        cast = tuple(CastEntry(**member) for member in data.get("cast", ()))
        return cls(
            plot=data["plot"],
            title=data.get("title", ""),
            genre=data.get("genre", ""),
            setting=data.get("setting", ""),
            cast=cast,
            notes=data.get("notes", ""),
        )


@dataclass(frozen=True, slots=True)
class BriefSpec:
    """The limits and choices the guided wizard offers, read from the generator."""

    limits: Mapping[str, int]
    max_cast: int
    roles: tuple[OptionChoice, ...]
    pronouns: tuple[OptionChoice, ...]


@dataclass(frozen=True, slots=True)
class RunSummary:
    """What a finished run reports back to the chat once artifacts are read."""

    usage: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    document_caption: str | None = None
    audio: bool = True
    audio_voice: str = ""


class GenerationFailure(Exception):
    """A generation failure that can be shown to a user as it stands.

    Adapters raise this for every failure they recognize. Anything else that
    escapes an adapter is an internal defect and the coordinator reports it as
    an unexpected error instead.
    """

    def __init__(
        self,
        summary: str,
        *,
        code: str,
        stage: str,
        recommendation: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """Store the safe, user-facing description of one failed generation."""
        super().__init__(summary)
        self.summary = summary
        self.code = code
        self.stage = stage
        self.recommendation = recommendation
        self.run_id = run_id

    def public_message(self) -> str:
        """Render the chat message describing this failure."""
        lines = [self.summary, f"Código: {self.code}."]
        if self.recommendation:
            lines.append("Sugerencia: " + self.recommendation)
        if self.run_id:
            lines.append(f"Ejecución: {self.run_id}.")
        return "\n".join(lines)


class GenerationCancelled(GenerationFailure):
    """Raised when a user cancels a generation that had already started."""

    def __init__(self, stage: str = "cancelled") -> None:
        """Describe a cancellation as the terminal state the user asked for."""
        super().__init__(
            "Cancelaste la generación.",
            code="CANCELLED_BY_USER",
            stage=stage,
        )


class GeneratorUnavailable(RuntimeError):
    """Report that an adapter could not be built from the current configuration.

    Kept in the application contract, instead of the pipeline's own error type,
    so that only generators.py needs to import the pipeline.
    """


ProgressCallback = Callable[[GenerationProgress], None]
EventCallback = Callable[[GenerationEvent], None]
RunCreatedCallback = Callable[[Path], None]
ShouldCancel = Callable[[], bool]


@runtime_checkable
class StoryGeneratorAdapter(Protocol):
    """The complete surface the bot uses to produce and describe one story."""

    @property
    def display_name(self) -> str:
        """Return the generator name shown to Telegram users."""
        ...

    @property
    def option_specs(self) -> tuple[OptionSpec, ...]:
        """Return every configurable run option, in panel order."""
        ...

    @property
    def brief_spec(self) -> BriefSpec:
        """Return the limits and choices the guided wizard offers."""
        ...

    def default_options(self) -> dict[str, OptionValue]:
        """Return this deployment's default value for every option."""
        ...

    def normalize_options(self, values: Mapping[str, OptionValue]) -> dict[str, OptionValue]:
        """Merge, resolve and validate a set of chosen option values.

        Unknown keys are ignored, so stored preferences survive an option being
        removed. Raises ValueError with a message the chat can show as it is.
        """
        ...

    def validate_outline(self, outline: StoryOutline) -> None:
        """Reject an outline the pipeline could not turn into a story brief."""
        ...

    def startup_details(self) -> tuple[tuple[str, str], ...]:
        """Return the (label, value) rows the operator console shows at start-up."""
        ...

    def generate(
        self,
        request: str | StoryOutline,
        *,
        options: Mapping[str, OptionValue] | None = None,
        on_progress: ProgressCallback | None = None,
        on_run_created: RunCreatedCallback | None = None,
        on_event: EventCallback | None = None,
        should_cancel: ShouldCancel | None = None,
    ) -> Path:
        """Generate one story and return its run directory."""
        ...

    def summarize(self, run_dir: Path) -> RunSummary:
        """Read a finished run and describe it for the chat."""
        ...
