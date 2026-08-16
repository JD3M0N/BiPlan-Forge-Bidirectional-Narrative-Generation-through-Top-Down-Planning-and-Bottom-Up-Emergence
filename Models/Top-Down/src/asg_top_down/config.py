"""Carga de configuración y resolución de rutas del proyecto.
La idea es cambiar el modelo o la API key sin modificar los agentes."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .errors import ConfigurationError


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    output_root: Path
    rpm_limit: int = 15
    rpm_reserve: int = 1
    tpm_limit: int = 0
    max_retries: int = 3
    max_retry_delay: int = 120
    default_target_words: int = 1500
    embedding_model: str = "gemini-embedding-2"
    max_cpn_retries: int = 2
    max_artifact_retries: int = 2


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "Models").is_dir() and (candidate / "Stories").is_dir():
            return candidate
    return Path(__file__).resolve().parents[4]


def load_settings(start: Path | None = None) -> Settings:
    root = find_project_root(start)
    load_dotenv(root / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ConfigurationError(
            "Falta GEMINI_API_KEY. Añádela al archivo .env de la raíz."
        )
    try:
        default_target_words = int(os.getenv("STORY_DEFAULT_WORDS", "1500"))
    except ValueError as exc:
        raise ConfigurationError(
            "STORY_DEFAULT_WORDS debe ser un número entero."
        ) from exc
    if not 300 <= default_target_words <= 20_000:
        raise ConfigurationError(
            "STORY_DEFAULT_WORDS debe estar entre 300 y 20000."
        )
    return Settings(
        api_key=api_key,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        or "gemini-2.5-flash",
        output_root=root / "Stories" / "Top-Down",
        rpm_limit=max(1, int(os.getenv("GEMINI_RPM_LIMIT", "15"))),
        rpm_reserve=max(0, int(os.getenv("GEMINI_RPM_RESERVE", "1"))),
        tpm_limit=max(0, int(os.getenv("GEMINI_TPM_LIMIT", "0"))),
        max_retries=max(1, int(os.getenv("GEMINI_MAX_RETRIES", "3"))),
        max_retry_delay=max(1, int(os.getenv("GEMINI_MAX_RETRY_DELAY", "120"))),
        default_target_words=default_target_words,
        embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2").strip()
        or "gemini-embedding-2",
        max_cpn_retries=max(0, int(os.getenv("STORY_MAX_CPN_RETRIES", "2"))),
        max_artifact_retries=max(0, int(os.getenv("STORY_MAX_ARTIFACT_RETRIES", "2"))),
    )
