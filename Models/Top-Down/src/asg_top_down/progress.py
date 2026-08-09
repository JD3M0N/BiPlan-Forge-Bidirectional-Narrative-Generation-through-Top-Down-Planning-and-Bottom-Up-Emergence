"""Progress notifications for Top-Down story generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class ProgressUpdate:
    """A completed generation milestone suitable for user interfaces."""

    percent: int
    stage: str
    description: str
    chapter: int | None = None
    total_chapters: int | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.percent <= 100:
            raise ValueError("percent must be between 0 and 100")


ProgressCallback = Callable[[ProgressUpdate], None]


def format_progress(update: ProgressUpdate, width: int = 10) -> str:
    """Render a compact, terminal- and chat-friendly progress bar."""

    filled = min(width, update.percent * width // 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {update.percent}% — {update.description}"
