"""Validate and persist human story evaluations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from asg_core import atomic_write_json

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
    """Handle the pending evaluation operation for component."""
    return {"user": None, **dict.fromkeys(METRICS)}


def _template() -> dict:
    """Handle the template operation for component."""
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluations": [_pending_evaluation()],
    }


def create_evaluation_template(story_directory: str | Path) -> Path:
    """Create a pending template without replacing an existing file."""
    directory = Path(story_directory)
    if not (directory / "story.md").is_file():
        raise ValueError(f"No existe story.md en {directory}")
    destination = directory / "evaluation.json"
    if not destination.exists():
        atomic_write_json(destination, _template())
    return destination


def _validate_complete(evaluation: object) -> dict:
    """Validate complete."""
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
    """Load the requested value."""
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
    """Append a complete evaluation while preserving previous entries."""
    if set(scores) != set(METRICS):
        raise ValueError(f"scores debe contener exactamente: {', '.join(METRICS)}")
    evaluation = _validate_complete({"user": user, **scores})
    destination = create_evaluation_template(story_directory)
    evaluations = _load(destination)
    evaluations.append(evaluation)
    atomic_write_json(
        destination,
        {"schema_version": SCHEMA_VERSION, "evaluations": evaluations},
    )
    return destination


def discover_stories(stories_root: str | Path) -> list[Path]:
    """Return story directories while excluding experiments without story.md."""
    root = Path(stories_root)
    if not root.is_dir():
        return []
    return sorted(path.parent for path in root.rglob("story.md") if path.is_file())
