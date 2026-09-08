"""Application-owned contract every story generator adapter must satisfy.

The bot speaks only these types. Keeping them here, instead of importing the
Top-Down pipeline types directly, means a second approach can be plugged in
without touching conversation, delivery or console code.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


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


@dataclass(frozen=True, slots=True)
class ProfileOption:
    """One selectable narrative profile with the label shown to the user."""

    value: str
    label: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RunSummary:
    """What a finished run reports back to the chat once artifacts are read."""

    usage: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


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


ProgressCallback = Callable[[GenerationProgress], None]
EventCallback = Callable[[GenerationEvent], None]
RunCreatedCallback = Callable[[Path], None]


@runtime_checkable
class StoryGeneratorAdapter(Protocol):
    """The complete surface the bot uses to produce and describe one story."""

    @property
    def display_name(self) -> str:
        """Return the generator name shown to Telegram users."""
        ...

    @property
    def profiles(self) -> tuple[ProfileOption, ...]:
        """Return the narrative profiles a user may choose between."""
        ...

    def generate(
        self,
        prompt: str,
        *,
        narrative_profile: str | None = None,
        on_progress: ProgressCallback | None = None,
        on_run_created: RunCreatedCallback | None = None,
        on_event: EventCallback | None = None,
    ) -> Path:
        """Generate one story and return its run directory."""
        ...

    def summarize(self, run_dir: Path) -> RunSummary:
        """Read a finished run and describe it for the chat."""
        ...


def format_progress(update: GenerationProgress, width: int = 10) -> str:
    """Render a compact, chat-friendly progress bar."""
    filled = min(width, update.percent * width // 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {update.percent}% — {update.description}"
