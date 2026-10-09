"""The progress bar every interface prints, shared so the console and the bot never drift."""

from __future__ import annotations

from typing import Protocol


class Progress(Protocol):
    """Anything that says how far a generation is and what it is doing."""

    @property
    def percent(self) -> int:
        """Completed share of the run, from 0 to 100."""
        ...

    @property
    def description(self) -> str:
        """What the run is doing now, in the user's language."""
        ...


def format_progress(update: Progress, width: int = 10) -> str:
    """Render a compact, terminal- and chat-friendly progress bar."""
    filled = min(width, update.percent * width // 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {update.percent}% — {update.description}"
