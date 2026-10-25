"""Tolerant readers shared by every report over the stored runs.

The reports read sidecar artifacts that older generator versions wrote differently or not at
all, so everything here treats a missing, broken or mistyped value as absent instead of failing.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

ErrorHandler = Callable[[Path, str], None]


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


def read_json_lines(path: Path) -> list[dict]:
    """Read valid JSON objects from an append-only log, tolerating a torn last line."""
    if not path.is_file():
        return []
    try:
        raw = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    found = []
    for line in raw:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            found.append(value)
    return found


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
