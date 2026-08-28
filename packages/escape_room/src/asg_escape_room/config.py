"""Load Bottom-Up runtime configuration shared with Top-Down conventions."""

import os
from dataclasses import dataclass
from pathlib import Path

from asg_core import find_project_root
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Represent Settings data and behavior."""

    api_key: str | None
    model: str
    output_root: Path


def load_settings(start: Path | None = None) -> Settings:
    """Load settings."""
    root = find_project_root(start)
    load_dotenv(root / ".env")
    return Settings(
        api_key=os.getenv("GEMINI_API_KEY", "").strip() or None,
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite",
        output_root=root / "Stories" / "Bottom-Up" / "Escape-Room",
    )
