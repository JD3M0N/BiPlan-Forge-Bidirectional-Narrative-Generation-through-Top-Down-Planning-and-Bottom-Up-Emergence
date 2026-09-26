"""Tolerant readers shared by every report over the stored runs.

The reports read sidecar artifacts that older generator versions wrote differently or not at
all, so everything here treats a missing, broken or mistyped value as absent instead of failing.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol, TypeVar

UNKNOWN = "desconocida"
NO_PROFILE = "sin perfil"

ErrorHandler = Callable[[Path, str], None]
Record = TypeVar("Record")


class RunAxes(Protocol):
    """The version, profile and format axes every stored-run record carries."""

    generator_version: str | None
    pipeline_version: str | None
    narrative_profile: str | None
    story_format: str
    script_method: str | None


def discover_runs(stories_root: str | Path, filename: str) -> list[Path]:
    """Return every directory below a root that holds one artifact, in a stable order."""
    root = Path(stories_root)
    if not root.is_dir():
        return []
    return sorted(path.parent for path in root.rglob(filename) if path.is_file())


def load_json_object(path: Path, on_error: ErrorHandler | None = None) -> dict:
    """Read one JSON object, treating a missing, broken or non-object file as empty.

    A file that exists but cannot be read or parsed is also reported through ``on_error``.
    """
    if not path.is_file():
        return {}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        if on_error is not None:
            on_error(path, str(error))
        return {}
    return document if isinstance(document, dict) else {}


def text_field(document: dict, field: str) -> str | None:
    """Read one non-empty string field, or None when it is absent."""
    value = document.get(field)
    return value if isinstance(value, str) and value.strip() else None


def number_field(document: dict, field: str) -> float | None:
    """Read one numeric field as a float, ignoring booleans and other types."""
    value = document.get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def record_version(record: RunAxes) -> str:
    """Pick the version axis that separates generator releases, not pipeline contracts."""
    return record.generator_version or record.pipeline_version or UNKNOWN


def record_profile(record: RunAxes) -> str:
    """Name the narrative profile of a run that may not declare one."""
    return record.narrative_profile or NO_PROFILE


def record_format(record: RunAxes) -> str:
    """Name the output format, and its method for a theater script."""
    if record.story_format == "script" and record.script_method:
        return f"script/{record.script_method}"
    return record.story_format


def group_by(records: Iterable[Record], key: Callable[[Record], str]) -> dict[str, list[Record]]:
    """Bucket records under their key, with the labels in sorted order."""
    grouped: dict[str, list[Record]] = {}
    for record in records:
        grouped.setdefault(key(record), []).append(record)
    return {label: grouped[label] for label in sorted(grouped)}
