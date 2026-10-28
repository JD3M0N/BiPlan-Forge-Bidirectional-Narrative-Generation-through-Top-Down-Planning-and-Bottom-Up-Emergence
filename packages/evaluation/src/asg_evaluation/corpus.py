"""Read-only inventory of the stored runs: which ones can be ranked and which are anomalies.

The inventory never writes to the corpus and never calls a model. A run is eligible for the
ranking when it completed, has a story, is prose and was written by Stagecraft 7 or later;
anything else is excluded with a written reason.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from asg_core import atomic_write_csv, atomic_write_json, use_utf8_output

from .artifacts import load_json_object, text_field
from .pairing import read_run_config

PROSE_FORMATS = frozenset({"baseline", "narrative", "simulated"})
FIRST_ELIGIBLE_MAJOR = 7
STUCK_AFTER = timedelta(hours=24)
IGNORED_FILES = frozenset({".gitkeep"})
COLUMNS = (
    "run",
    "family",
    "story_format",
    "format_inferred",
    "pipeline_version",
    "generator_version",
    "status",
    "has_story",
    "eligible",
    "reason",
)


def _major(pipeline_version: str | None) -> int | None:
    """Read the major number of a pipeline version, or None when it is absent or odd."""
    try:
        return int((pipeline_version or "").split(".")[0])
    except ValueError:
        return None


def exclusion_reason(
    status: str | None,
    story_format: str | None,
    pipeline_version: str | None,
    *,
    has_story: bool = True,
) -> str:
    """Return why a run cannot enter the ranking, or an empty string when it can."""
    if status != "completed":
        return "Run no completado"
    if not has_story:
        return "Sin story.md"
    if story_format not in PROSE_FORMATS:
        return "Formato fuera del estudio en prosa"
    major = _major(pipeline_version)
    if major is None or major < FIRST_ELIGIBLE_MAJOR:
        return "Generador anterior a Stagecraft 7"
    return ""


def _parse_time(value: object) -> datetime | None:
    """Parse an ISO timestamp as UTC-aware, or None when it is missing or broken."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _run_row(run_dir: Path, family: str, rel: str, now: datetime) -> tuple[dict, list[dict]]:
    """Describe one run and the anomalies it carries."""
    config = read_run_config(run_dir)
    metadata = load_json_object(run_dir / "metadata.json")
    has_story = (run_dir / "story.md").is_file()
    story_format = config.axes.get("story_format")
    inferred = text_field(metadata, "story_format") is None and (
        config.sources.get("story_format") != "generation_options.json"
    )
    reason = exclusion_reason(
        config.status, story_format, config.pipeline_version, has_story=has_story
    )
    row = {
        "run": rel,
        "family": family,
        "story_format": story_format,
        "format_inferred": inferred,
        "pipeline_version": config.pipeline_version,
        "generator_version": config.generator_version,
        "status": config.status,
        "has_story": has_story,
        "eligible": not reason,
        "reason": reason,
    }
    found: list[dict] = []

    def note(kind: str, detail: str = "") -> None:
        """Record one anomaly of this run."""
        found.append({"path": rel, "kind": kind, "detail": detail})

    if config.pipeline_version is None:
        note("sin_version_de_pipeline")
    if not (run_dir / "generator_version.json").is_file():
        note("sin_generator_version")
    if inferred:
        note("formato_inferido", str(story_format))
    if config.status == "failed" and has_story:
        note("failed_con_story")
    if config.status == "running":
        stamp = _parse_time(metadata.get("updated_at")) or _parse_time(metadata.get("created_at"))
        if stamp is None or now - stamp > STUCK_AFTER:
            note("running_atascado", str(metadata.get("updated_at")))
    for tmp in sorted(run_dir.rglob("*.tmp")):
        note("tmp_suelto", tmp.relative_to(run_dir).as_posix())
    return row, found


def _walk(directory: Path, root: Path, family: str, now: datetime, rows: list, anomalies: list):
    """Collect runs below a directory; the highest folder without runs is one anomaly."""
    for child in sorted(directory.iterdir()):
        rel = child.relative_to(root).as_posix()
        if child.is_file():
            if child.name not in IGNORED_FILES:
                anomalies.append({"path": rel, "kind": "no_es_run", "detail": "archivo"})
        elif (child / "metadata.json").is_file():
            row, found = _run_row(child, family, rel, now)
            rows.append(row)
            anomalies.extend(found)
        elif any(child.rglob("metadata.json")):
            _walk(child, root, family, now, rows, anomalies)
        else:
            anomalies.append({"path": rel, "kind": "no_es_run", "detail": "carpeta sin runs"})


def scan(root: str | Path, now: datetime | None = None) -> dict:
    """Inventory every run below ``root``'s family folders, reading only."""
    root = Path(root)
    now = now or datetime.now(UTC)
    rows: list[dict] = []
    anomalies: list[dict] = []
    for family in sorted(p for p in root.iterdir() if p.is_dir()):
        _walk(family, root, family.name, now, rows, anomalies)
    kinds = Counter(a["kind"] for a in anomalies)
    return {
        "root": str(root),
        "summary": {
            "runs": len(rows),
            "eligible": sum(r["eligible"] for r in rows),
            "excluded": dict(Counter(r["reason"] for r in rows if r["reason"])),
            "status": dict(Counter(r["status"] for r in rows)),
            "anomalies": dict(kinds),
        },
        "runs": rows,
        "anomalies": anomalies,
    }


def main(argv: list[str] | None = None) -> int:
    """Print the corpus inventory and optionally save it, without writing to the corpus."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Inventario del corpus de historias")
    parser.add_argument("root", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        print("No existe la carpeta de historias.", file=sys.stderr)
        return 1
    report = scan(args.root)
    if args.json:
        atomic_write_json(args.json, report)
    if args.csv:
        atomic_write_csv(
            args.csv, COLUMNS, [[row[key] for key in COLUMNS] for row in report["runs"]]
        )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0
