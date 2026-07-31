"""Carga de configuración compartida con el proyecto."""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
from .errors import ConfigurationError

@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str

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
        raise ConfigurationError("Falta GEMINI_API_KEY. Añádela al archivo .env de la raíz.")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    return Settings(api_key=api_key, model=model or "gemini-2.5-flash")
