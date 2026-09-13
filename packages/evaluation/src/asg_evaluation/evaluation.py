"""Validate and persist human story evaluations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from asg_core import atomic_write_json, file_lock

METRICS = (
    "coherence",
    "pacing",
    "creativity",
    "engagement",
    "relevance",
    "satisfaction",
)
SCHEMA_VERSION = 1
EVALUATION_FILENAME = "evaluation.json"


def _pending_evaluation() -> dict[str, str | int | None]:
    """Build the placeholder entry written next to a story without scores."""
    return {"user": None, **dict.fromkeys(METRICS)}


def _template() -> dict:
    """Build the document stored for a story that nobody has evaluated yet."""
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluations": [_pending_evaluation()],
    }


def _evaluation_path(story_directory: str | Path) -> Path:
    """Locate the evaluation file of a story directory that holds a story.md."""
    directory = Path(story_directory)
    if not (directory / "story.md").is_file():
        raise ValueError(f"No existe story.md en {directory}")
    return directory / EVALUATION_FILENAME


def _ensure_template(destination: Path) -> Path:
    """Write the pending template unless the file already exists."""
    if not destination.exists():
        atomic_write_json(destination, _template())
    return destination


def create_evaluation_template(story_directory: str | Path) -> Path:
    """Create a pending template without replacing an existing file."""
    destination = _evaluation_path(story_directory)
    with file_lock(destination):
        return _ensure_template(destination)


def _is_pending(entry: object) -> bool:
    """Report whether an entry is a placeholder still waiting for its scores.

    Only the six scores decide: an evaluator who wrote their name and left the scoring for
    later still holds a placeholder, and that file must keep accepting evaluations.
    """
    if not isinstance(entry, dict):
        return False
    return all(entry.get(metric) is None for metric in METRICS)


def _validate_complete(evaluation: object, *, index: int | None = None) -> dict:
    """Normalize one complete evaluation or explain precisely why it is not."""
    where = "" if index is None else f"evaluación {index}: "
    if not isinstance(evaluation, dict):
        raise ValueError(f"{where}cada evaluación debe ser un objeto JSON")
    unknown = sorted(set(evaluation) - {"user", *METRICS})
    if unknown:
        raise ValueError(f"{where}campos desconocidos: {', '.join(unknown)}")
    missing = [metric for metric in ("user", *METRICS) if metric not in evaluation]
    if missing:
        raise ValueError(f"{where}faltan campos: {', '.join(missing)}")
    user = evaluation["user"]
    if not isinstance(user, str) or not user.strip():
        raise ValueError(f"{where}user debe ser una cadena no vacía")
    normalized = {"user": user.strip()}
    for metric in METRICS:
        score = evaluation[metric]
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 10:
            raise ValueError(f"{where}{metric} debe ser un entero entre 1 y 10")
        normalized[metric] = score
    return normalized


def _load(path: Path) -> list[dict]:
    """Read the stored evaluations, dropping placeholders wherever they appear."""
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
    return [
        _validate_complete(entry, index=index)
        for index, entry in enumerate(document["evaluations"], start=1)
        if not _is_pending(entry)
    ]


def add_evaluation(
    story_directory: str | Path,
    user: str,
    scores: Mapping[str, int],
) -> Path:
    """Append a complete evaluation while preserving previous entries."""
    if set(scores) != set(METRICS):
        raise ValueError(f"scores debe contener exactamente: {', '.join(METRICS)}")
    evaluation = _validate_complete({"user": user, **scores})
    destination = _evaluation_path(story_directory)
    try:
        with file_lock(destination):
            _ensure_template(destination)
            evaluations = _load(destination)
            evaluations.append(evaluation)
            atomic_write_json(
                destination,
                {"schema_version": SCHEMA_VERSION, "evaluations": evaluations},
            )
    except TimeoutError as exc:
        raise TimeoutError(
            f"Otra evaluación está escribiendo {destination}; inténtalo de nuevo."
        ) from exc
    return destination


def discover_stories(stories_root: str | Path) -> list[Path]:
    """Return story directories while excluding experiments without story.md."""
    root = Path(stories_root)
    if not root.is_dir():
        return []
    return sorted(path.parent for path in root.rglob("story.md") if path.is_file())
