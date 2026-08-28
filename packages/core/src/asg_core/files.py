"""Atomic UTF-8 file persistence helpers."""

from __future__ import annotations

import json
import os
import tempfile
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


def atomic_write_json(destination: str | Path, data: Any) -> Path:
    """Atomically serialize JSON data using the repository format."""
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return atomic_write_text(destination, content)
