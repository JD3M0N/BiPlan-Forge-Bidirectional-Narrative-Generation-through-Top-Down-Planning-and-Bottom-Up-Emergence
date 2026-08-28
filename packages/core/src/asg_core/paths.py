"""Project paths and filesystem-safe naming helpers."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path


def find_project_root(start: str | Path | None = None) -> Path:
    """Locate the ASG repository root from an optional starting path."""
    configured = os.getenv("ASG_PROJECT_ROOT", "").strip()
    current = Path(configured or start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "Stories").is_dir() and (candidate / "packages").is_dir():
            return candidate
    package_root = Path(__file__).resolve().parents[4]
    if (package_root / "Stories").is_dir():
        return package_root
    raise RuntimeError("Could not locate the ASG project root")


def stories_path(*parts: str, root: str | Path | None = None) -> Path:
    """Build a path below the repository's Stories directory."""
    project_root = Path(root).resolve() if root is not None else find_project_root()
    return project_root.joinpath("Stories", *parts)


def slugify(value: str, *, fallback: str = "item", max_length: int = 60) -> str:
    """Convert text into a short ASCII slug suitable for directory names."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")[:max_length]
    return slug or fallback
