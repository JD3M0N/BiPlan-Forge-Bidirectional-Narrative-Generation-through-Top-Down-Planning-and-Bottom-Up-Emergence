"""Configuration loading for Top-Down 5.0."""

import os
from dataclasses import dataclass
from pathlib import Path

from asg_core import find_project_root
from dotenv import load_dotenv

from .errors import ConfigurationError


@dataclass(frozen=True)
class Settings:
    """Represent Settings data and behavior."""

    api_key: str
    model: str
    output_root: Path
    rpm_limit: int = 15
    rpm_reserve: int = 1
    tpm_limit: int = 0
    max_retries: int = 3
    max_retry_delay: int = 120
    request_timeout_ms: int = 120_000
    default_target_words: int = 1500


def _integer(name: str, default: int, *, minimum: int = 0) -> int:
    """Handle the integer operation for component."""
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ConfigurationError(f"{name} debe ser un número entero.") from exc
    if value < minimum:
        raise ConfigurationError(f"{name} debe ser al menos {minimum}.")
    return value


def load_settings(start: Path | None = None) -> Settings:
    """Load settings."""
    root = find_project_root(start)
    load_dotenv(root / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError("Falta GEMINI_API_KEY. Añádela al archivo .env de la raíz.")
    default_target_words = _integer("STORY_DEFAULT_WORDS", 1500, minimum=300)
    if default_target_words > 20_000:
        raise ConfigurationError("STORY_DEFAULT_WORDS debe estar entre 300 y 20000.")
    return Settings(
        api_key=api_key,
        model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip() or "gemini-3.5-flash-lite",
        output_root=root / "Stories" / "Top-Down",
        rpm_limit=_integer("GEMINI_RPM_LIMIT", 15, minimum=1),
        rpm_reserve=_integer("GEMINI_RPM_RESERVE", 1),
        tpm_limit=_integer("GEMINI_TPM_LIMIT", 0),
        max_retries=_integer("GEMINI_MAX_RETRIES", 3),
        max_retry_delay=_integer("GEMINI_MAX_RETRY_DELAY", 120, minimum=1),
        request_timeout_ms=_integer("GEMINI_REQUEST_TIMEOUT_MS", 120_000, minimum=5_000),
        default_target_words=default_target_words,
    )
