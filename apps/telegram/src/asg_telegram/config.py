"""Load the bot configuration from the root .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from asg_core import find_project_root
from dotenv import load_dotenv

DEFAULT_STUDY = "Evaluations/estudio/study.sqlite3"
# Each participant's comparison of their own two stories, next to the blind study.
DEFAULT_PAIRS = "Evaluations/estudio/pares_propios.sqlite3"


class TelegramConfigurationError(RuntimeError):
    """Report missing or invalid Telegram configuration."""


@dataclass(frozen=True)
class TelegramSettings:
    """Hold the bot token and where the queue, the study and the own pairs live."""

    token: str = field(repr=False)
    project_root: Path
    study_path: Path
    queue_path: Path
    pairs_path: Path


def load_settings(start: Path | None = None, *, need_token: bool = True) -> TelegramSettings:
    """Read the token and the study paths from the root .env, resolving paths from the root."""
    root = find_project_root(start)
    load_dotenv(root / ".env")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if need_token and not token:
        raise TelegramConfigurationError(
            "Falta TELEGRAM_BOT_TOKEN. Añádelo al archivo .env de la raíz."
        )
    return TelegramSettings(
        token,
        root,
        _path(root, "ASG_EVALUATION_STUDY", DEFAULT_STUDY),
        root / "Stories" / "telegram_jobs.sqlite3",
        _path(root, "ASG_OWN_PAIRS", DEFAULT_PAIRS),
    )


def _path(root: Path, variable: str, default: str) -> Path:
    """Resolve a path variable from the .env against the project root."""
    path = Path(os.getenv(variable, "").strip() or default)
    return (path if path.is_absolute() else root / path).resolve()
