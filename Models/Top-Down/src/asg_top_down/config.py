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
    )
