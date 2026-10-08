"""Load bot configuration and resolve the project root."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from asg_core import find_project_root
from dotenv import load_dotenv


class TelegramConfigurationError(RuntimeError):
    """Report missing or invalid Telegram configuration."""


@dataclass(frozen=True)
class TelegramSettings:
    """Hold the bot token, generator, access key and study database location."""

    telegram_token: str
    generator_name: str
    project_root: Path
    access_key: str = field(repr=False)
    study_path: Path


def load_settings(start: Path | None = None) -> TelegramSettings:
    """Read the root .env and reject a bot that could run outside the experiment."""
    root = find_project_root(start)
    load_dotenv(root / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise TelegramConfigurationError(
            "Falta TELEGRAM_BOT_TOKEN. Añádelo al archivo .env de la raíz."
        )
    generator_name = os.getenv("STORY_GENERATOR", "stagecraft").strip().lower()
    access_key = os.getenv("TELEGRAM_ACCESS_KEY", "").strip()
    if not access_key:
        raise TelegramConfigurationError(
            "Falta TELEGRAM_ACCESS_KEY. Define en .env la clave que entregarás a los "
            "participantes del estudio."
        )
    study = os.getenv("ASG_EVALUATION_STUDY", "").strip()
    if not study:
        raise TelegramConfigurationError(
            "Falta ASG_EVALUATION_STUDY. Crea el estudio con evaluation-study create y "
            "apunta esta variable a su base de datos."
        )
    study_path = Path(study)
    if not study_path.is_absolute():
        study_path = root / study_path
    if not study_path.is_file():
        raise TelegramConfigurationError(
            f"No existe la base del estudio {study_path}. Créala con evaluation-study create."
        )
    return TelegramSettings(
        token, generator_name or "stagecraft", root, access_key, study_path.resolve()
    )
