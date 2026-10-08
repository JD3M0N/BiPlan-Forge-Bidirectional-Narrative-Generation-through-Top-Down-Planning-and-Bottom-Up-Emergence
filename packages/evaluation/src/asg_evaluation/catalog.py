"""Versioned feature definitions shared with the thesis spreadsheet."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from importlib.resources import files
from pathlib import Path

CATALOG_VERSION = 1
CRITERIA = ("H01", "H02", "H03")


def resource_text(name: str) -> str:
    """Read the canonical CSV in editable installs or its packaged wheel resource."""
    source = Path(__file__).resolve().parents[2] / "planilla" / name
    if source.is_file():
        return source.read_text(encoding="utf-8")
    return files("asg_evaluation").joinpath("data", name).read_text(encoding="utf-8")


def catalog() -> dict[str, dict[str, str]]:
    """Return every feature keyed by its stable spreadsheet identifier."""
    return {row["id"]: row for row in csv.DictReader(io.StringIO(resource_text("rasgos.csv")))}


def core_ids() -> list[str]:
    """Select text features only, excluding process and target fields marked as core."""
    return [
        key
        for key, row in catalog().items()
        if row["capa"] in {"T", "R", "X"} and row["prioridad"] == "núcleo"
    ]


def questions() -> dict[str, str]:
    """Return the tutor's exact three comparison questions."""
    return {
        row["id"]: row["pregunta"]
        for row in csv.DictReader(io.StringIO(resource_text("criterios_humanos.csv")))
    }


def guidance() -> dict[str, str]:
    """Return what a reader should look at for each comparison criterion."""
    return {
        row["id"]: row["que_mirar"]
        for row in csv.DictReader(io.StringIO(resource_text("criterios_humanos.csv")))
    }


def digest(value: object) -> str:
    """Hash a canonical JSON value, without depending on dictionary order."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


def catalog_snapshot() -> dict:
    """Freeze definitions, questions and the model input selection together."""
    data = {
        "version": CATALOG_VERSION,
        "features": catalog(),
        "questions": questions(),
        "core_ids": core_ids(),
    }
    return {**data, "sha256": digest(data)}
