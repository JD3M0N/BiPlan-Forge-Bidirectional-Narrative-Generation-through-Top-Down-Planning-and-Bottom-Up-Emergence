"""Validación y persistencia de evaluaciones humanas."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Mapping

METRICS = (
    "coherence",
    "pacing",
    "creativity",
    "engagement",
    "relevance",
    "satisfaction",
)
SCHEMA_VERSION = 1


def _pending_evaluation() -> dict[str, str | int | None]:
    return {"user": None, **dict.fromkeys(METRICS)}


def _template() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluations": [_pending_evaluation()],
    }


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def create_evaluation_template(story_directory: str | Path) -> Path:
    """Crea la plantilla pendiente sin reemplazar un archivo existente."""
    directory = Path(story_directory)
    if not (directory / "story.md").is_file():
        raise ValueError(f"No existe story.md en {directory}")
    destination = directory / "evaluation.json"
    if not destination.exists():
        _atomic_write(destination, _template())
    return destination


def _validate_complete(evaluation: object) -> dict:
    if not isinstance(evaluation, dict):
        raise ValueError("Cada evaluación debe ser un objeto JSON")
    expected = {"user", *METRICS}
    if set(evaluation) != expected:
        raise ValueError("La evaluación contiene campos desconocidos o incompletos")
    user = evaluation["user"]
    if not isinstance(user, str) or not user.strip():
        raise ValueError("user debe ser una cadena no vacía")
    normalized = {"user": user.strip()}
    for metric in METRICS:
        score = evaluation[metric]
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 10:
            raise ValueError(f"{metric} debe ser un entero entre 1 y 10")
        normalized[metric] = score
    return normalized


def _load(path: Path) -> list[dict]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"No se pudo leer {path}: {exc}") from exc
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != SCHEMA_VERSION
        or not isinstance(document.get("evaluations"), list)
    ):
        raise ValueError("Formato de evaluation.json no reconocido")
    evaluations = document["evaluations"]
    if evaluations == [_pending_evaluation()]:
        return []
    return [_validate_complete(item) for item in evaluations]


def add_evaluation(
    story_directory: str | Path,
    user: str,
    scores: Mapping[str, int],
) -> Path:
    """Agrega una evaluación completa y conserva las evaluaciones anteriores."""
    if set(scores) != set(METRICS):
        raise ValueError(f"scores debe contener exactamente: {', '.join(METRICS)}")
    evaluation = _validate_complete({"user": user, **scores})
    destination = create_evaluation_template(story_directory)
    evaluations = _load(destination)
    evaluations.append(evaluation)
    _atomic_write(
        destination,
        {"schema_version": SCHEMA_VERSION, "evaluations": evaluations},
    )
    return destination


def discover_stories(stories_root: str | Path) -> list[Path]:
    """Devuelve carpetas de historias, excluyendo experimentos sin story.md."""
    root = Path(stories_root)
    if not root.is_dir():
        return []
    return sorted(path.parent for path in root.rglob("story.md") if path.is_file())


def migrate_story_evaluations(stories_root: str | Path) -> list[Path]:
    """Crea de forma idempotente las plantillas que falten."""
    return [create_evaluation_template(path) for path in discover_stories(stories_root)]
