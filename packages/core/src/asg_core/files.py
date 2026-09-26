"""Atomic UTF-8 file persistence helpers."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


def atomic_write_text(destination: str | Path, content: str) -> Path:
    """Atomically replace a text file with UTF-8 content."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return path


def artifact_json(data: Any) -> str:
    """Serialize data in the repository JSON format: UTF-8, indented, newline-terminated.

    Exposed apart from the writer for callers that must hash exactly what reaches disk.
    """
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def atomic_write_json(destination: str | Path, data: Any) -> Path:
    """Atomically serialize JSON data using the repository format."""
    return atomic_write_text(destination, artifact_json(data))


def atomic_write_csv(
    destination: str | Path,
    header: Sequence[object],
    rows: Iterable[Sequence[object]],
) -> Path:
    """Atomically write a CSV table, header first, in the csv module's default dialect."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return atomic_write_text(destination, buffer.getvalue())
