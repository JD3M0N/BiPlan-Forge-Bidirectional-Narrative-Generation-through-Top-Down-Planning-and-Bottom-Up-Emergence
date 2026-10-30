"""Pair derived runs with their source plan from a matrix manifest, without model calls."""

from __future__ import annotations

import csv
import io
import statistics
from collections import defaultdict
from pathlib import PurePosixPath

from .catalog import catalog, core_ids

DONE = "completed"
MIN_PAIRS = 6
NOT_MEASURED = "no medido"
NOT_NUMERIC = "no numérico"
INTERPRETATION = (
    "Asociaciones observacionales emparejadas por plan fuente (derivada menos fuente); no se "
    "atribuyen causas. «Dentro del ruido» y «n insuficiente» no se interpretan."
)
COLUMNS = (
    "pipeline_version",
    "celda",
    "eje",
    "nivel",
    "tipo",
    "rasgo",
    "nucleo",
    "n",
    "mediana",
    "minimo",
    "maximo",
    "lectura",
)


def feature_order() -> list[str]:
    """List the core features first, then the process (P) and cost (K) ones."""
    keys = catalog()
    return [
        *core_ids(),
        *(key for key in keys if key.startswith("P")),
        *(key for key in keys if key.startswith("K")),
    ]


def cell_labels(matrix_text: str | None) -> dict[str, tuple[str, str]]:
    """Map each matrix cell to its axis and level; empty when the matrix is not given."""
    if not matrix_text:
        return {}
    rows = csv.DictReader(io.StringIO(matrix_text.lstrip("﻿")))
    return {row["celda"]: (row.get("eje", ""), row.get("nivel", "")) for row in rows}


def _name(path: str) -> str:
    """Return the run directory name of a path stored with either separator."""
    return PurePosixPath(path.replace("\\", "/")).name


def _value(row: dict, key: str) -> float | None:
    """Return a measured numeric value, or None."""
    feature = row["features"].get(key)
    if not feature or feature.get("status") != "measured":
        return None
    value = feature.get("value")
    return value if isinstance(value, int | float) else None


def _measured(row: dict, key: str) -> bool:
    """Say whether a feature was measured at all, numeric or not."""
    feature = row["features"].get(key)
    return bool(feature) and feature.get("status") == "measured"


def _noise(entries: dict[str, dict], rows: dict[str, dict], keys: list[str]) -> dict:
    """Compute the largest repetition spread of each feature across the works of the bases."""
    by_work: dict[str, list[dict]] = defaultdict(list)
    for entry in entries.values():
        row = rows.get(_name(entry["run"] or ""))
        if entry["estado"] == DONE and not entry["fuente"] and entry["tipo"] != "baseline" and row:
            by_work[entry["obra"]].append(row)
    noise = {}
    for key in keys:
        spreads = []
        for runs in by_work.values():
            values = [_value(run, key) for run in runs]
            if len(values) >= 2 and None not in values:
                spreads.append(max(values) - min(values))
        noise[key] = {"valor": max(spreads), "obras": len(spreads)} if spreads else None
    return noise


def _reading(diffs: list[float], noise: dict | None) -> str:
    """Apply the noise rule fixed in decisions.md to a list of paired differences."""
    if len(diffs) < MIN_PAIRS:
        return "n insuficiente"
    if noise is None:
        return "sin ruido medido"
    median = statistics.median(diffs)
    if median == 0:
        return "dentro del ruido"
    agree = sum(1 for d in diffs if d * median > 0)
    inside = abs(median) <= noise["valor"] or agree < len(diffs) - 1
    return "dentro del ruido" if inside else "interpretable"


def _stats(numbers: list[float], rows: list[dict], key: str, kind: str, noise: dict | None) -> dict:
    """Summarize one feature of one cell; label what was not measured."""
    if numbers:
        reading = _reading(numbers, noise) if kind == "pares" else ""
        return {
            "n": len(numbers),
            "mediana": statistics.median(numbers),
            "minimo": min(numbers),
            "maximo": max(numbers),
            "lectura": reading,
        }
    measured = any(_measured(r, key) for r in rows)
    reading = NOT_NUMERIC if measured else NOT_MEASURED
    return {"n": 0, "mediana": None, "minimo": None, "maximo": None, "lectura": reading}


def _source_of(
    row: dict, entries: dict, by_name: dict, pipeline: str, source_id: str
) -> tuple[dict | None, str | None]:
    """Find a derived run's source row, or say why the pair cannot be trusted."""
    source_entry = entries.get(source_id, {})
    source = by_name.get(_name(source_entry.get("run") or ""))
    recorded = row["features"].get("C18", {})
    if source_entry.get("estado") != DONE or source is None:
        return None, "fuente sin informe de rasgos"
    if recorded.get("status") != "measured":
        return None, "sin source_run.json (C18)"
    if recorded.get("value") != source["run_id"]:
        return None, "C18 no coincide con la fuente del manifiesto"
    if str(source["pipeline_version"]) != pipeline:
        return None, "pipeline distinto del de la fuente"
    return source, None


def paired_report(
    rows: list[dict], manifest: dict, labels: dict[str, tuple[str, str]] | None = None
) -> dict:
    """Report the difference of each feature between derived runs and their source run."""
    labels = labels or {}
    by_name = {row["run_id"]: row for row in rows}
    entries: dict[str, dict] = manifest.get("units", {})
    keys = feature_order()
    core = set(core_ids())
    noise = _noise(entries, by_name, keys)
    discarded: list[dict] = []
    cells: dict[tuple[str, str, str], dict] = {}

    def add(pipeline: str, cell: str, kind: str, pair: tuple[dict, dict | None]) -> None:
        """File one run, or one derived-source pair, under its pipeline group and cell."""
        slot = cells.setdefault((pipeline, cell, kind), {"pairs": []})
        slot["pairs"].append(pair)

    for unit_id, entry in entries.items():
        if entry["estado"] != DONE or not entry["run"]:
            continue
        row = by_name.get(_name(entry["run"]))
        if row is None:
            discarded.append({"unidad": unit_id, "motivo": "sin informe de rasgos"})
            continue
        pipeline = str(row["pipeline_version"])
        if not entry["fuente"]:
            add(
                pipeline,
                entry["celda"],
                "linea_base" if entry["tipo"] == "baseline" else "base",
                (row, None),
            )
            continue
        source, reason = _source_of(row, entries, by_name, pipeline, entry["fuente"])
        if reason:
            discarded.append({"unidad": unit_id, "motivo": reason})
            continue
        add(pipeline, entry["celda"], "pares", (row, source))

    groups: dict[str, dict] = {}
    for (pipeline, cell, kind), slot in sorted(cells.items()):
        pairs = slot["pairs"]
        members = [pair[0] for pair in pairs]
        features = []
        for key in keys:
            if kind == "pares":
                numbers = [
                    _value(d, key) - _value(s, key)
                    for d, s in pairs
                    if _value(d, key) is not None and _value(s, key) is not None
                ]
            else:
                numbers = [v for r in members if (v := _value(r, key)) is not None]
            features.append(
                {"id": key, "nucleo": key in core} | _stats(numbers, members, key, kind, noise[key])
            )
        eje, nivel = labels.get(cell, ("", ""))
        group = groups.setdefault(
            pipeline, {"pipeline_version": pipeline, "generator_versions": set(), "cells": []}
        )
        group["generator_versions"].update(str(r["generator_version"]) for r in members)
        group["cells"].append(
            {"celda": cell, "eje": eje, "nivel": nivel, "tipo": kind, "unidades": len(pairs)}
            | {"features": features}
        )
    ordered = [
        group | {"generator_versions": sorted(group["generator_versions"])}
        for _, group in sorted(groups.items())
    ]
    return {
        "paired": True,
        "matriz": manifest.get("matriz"),
        "ruido": noise,
        "groups": ordered,
        "descartadas": discarded,
        "interpretation": INTERPRETATION,
    }


def paired_rows(report: dict) -> list[list]:
    """Flatten a paired report into CSV rows, one per pipeline, cell and feature."""
    table = []
    for group in report["groups"]:
        for cell in group["cells"]:
            for feature in cell["features"]:
                table.append(
                    [
                        group["pipeline_version"],
                        cell["celda"],
                        cell["eje"],
                        cell["nivel"],
                        cell["tipo"],
                        feature["id"],
                        feature["nucleo"],
                        feature["n"],
                        feature["mediana"],
                        feature["minimo"],
                        feature["maximo"],
                        feature["lectura"],
                    ]
                )
    return table
