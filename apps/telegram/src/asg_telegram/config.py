"""Load bot configuration and resolve the project root."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from asg_core import find_project_root
from dotenv import load_dotenv


class TelegramConfigurationError(RuntimeError):
    """Report missing or invalid Telegram configuration."""


@dataclass(frozen=True)
class TelegramSettings:
    """Represent TelegramSettings data and behavior."""

    telegram_token: str
    generator_name: str
    project_root: Path


def load_settings(start: Path | None = None) -> TelegramSettings:
    """Load settings."""
    root = find_project_root(start)
    load_dotenv(root / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise TelegramConfigurationError(
            "Falta TELEGRAM_BOT_TOKEN. Añádelo al archivo .env de la raíz."
        )
    generator_name = os.getenv("STORY_GENERATOR", "top-down").strip().lower()
    return TelegramSettings(token, generator_name or "top-down", root)
