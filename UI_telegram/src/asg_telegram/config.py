"""Configuración del bot y resolución de la raíz del proyecto."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class TelegramConfigurationError(RuntimeError):
    """Configuración ausente o inválida."""


@dataclass(frozen=True)
class TelegramSettings:
    telegram_token: str
    generator_name: str
    project_root: Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "Models").is_dir() and (candidate / "Stories").is_dir():
            return candidate
    return Path(__file__).resolve().parents[4]


def load_settings(start: Path | None = None) -> TelegramSettings:
    root = find_project_root(start)
    load_dotenv(root / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise TelegramConfigurationError(
            "Falta TELEGRAM_BOT_TOKEN. Añádelo al archivo .env de la raíz."
        )
    generator_name = os.getenv("STORY_GENERATOR", "top-down").strip().lower()
    return TelegramSettings(token, generator_name or "top-down", root)
