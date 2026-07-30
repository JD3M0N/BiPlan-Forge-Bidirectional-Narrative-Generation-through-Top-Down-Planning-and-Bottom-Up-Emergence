"""Configuración compartida por convención con Top-Down."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    output_root: Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "Models").is_dir() and (candidate / "Stories").is_dir():
            return candidate
    return Path(__file__).resolve().parents[4]


def load_settings(start: Path | None = None) -> Settings:
    root = find_project_root(start)
    load_dotenv(root / ".env")
    return Settings(
        api_key=os.getenv("GEMINI_API_KEY", "").strip() or None,
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
        or "gemini-3.5-flash-lite",
        output_root=root / "Stories" / "Bottom-Up" / "Escape-Room",
    )

