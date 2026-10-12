"""Load the bot configuration from the root .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from asg_core import find_project_root
from dotenv import load_dotenv

DEFAULT_STUDY = "Evaluations/estudio/study.sqlite3"


class TelegramConfigurationError(RuntimeError):
    """Report missing or invalid Telegram configuration."""


@dataclass(frozen=True)
class TelegramSettings:
    """Hold the bot token and where the queue and the study live."""

    token: str = field(repr=False)
    project_root: Path
    study_path: Path
    queue_path: Path


def load_settings(start: Path | None = None) -> TelegramSettings:
    """Read TELEGRAM_BOT_TOKEN and ASG_EVALUATION_STUDY, resolving paths from the root."""
    root = find_project_root(start)
    load_dotenv(root / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise TelegramConfigurationError(
            "Falta TELEGRAM_BOT_TOKEN. Añádelo al archivo .env de la raíz."
        )
    study = Path(os.getenv("ASG_EVALUATION_STUDY", "").strip() or DEFAULT_STUDY)
    study = study if study.is_absolute() else root / study
    return TelegramSettings(
        token, root, study.resolve(), root / "Stories" / "telegram_jobs.sqlite3"
    )
