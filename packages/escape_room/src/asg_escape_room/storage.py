"""Auditable persistence for simulations and batch experiments."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from asg_core import atomic_write_json, atomic_write_text, slugify
from pydantic import BaseModel

from .contracts import SimulationResult, TickRecord


def _timestamped_directory(root: Path, name: str) -> Path:
    """Create a fresh directory under root, suffixing the name until it does not exist."""
    directory = root / name
    suffix = 2
    while directory.exists():
        directory = root / f"{name}-{suffix}"
        suffix += 1
    directory.mkdir(parents=True)
    return directory


def _package_version() -> str:
    """Report the installed asg-escape-room version, or "unknown" outside an install."""
    try:
        return version("asg-escape-room")
    except PackageNotFoundError:
        return "unknown"


class RunRepository:
    """Represent RunRepository data and behavior."""

    def __init__(self, root: Path, room_name: str, model: str) -> None:
        """Initialize the RunRepository instance."""
        now = datetime.now(UTC)
        base = f"{now.strftime('%Y%m%d-%H%M%S')}-{slugify(room_name, fallback='escape-room')}"
        self.run_dir = _timestamped_directory(root, base)
        self.metadata = {
            "run_id": self.run_dir.name,
            "model": model,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "status": "running",
            "completed_stages": [],
            "narrator": None,
            "narrative_error": None,
            "audio_status": None,
            "audio_error": None,
            "error": None,
        }
        self._metadata()

    def save_json(self, name: str, value: BaseModel | dict | list) -> None:
        """Save json."""
        data = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        (self.run_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def save_ticks(self, records: Iterable[TickRecord]) -> None:
        """Save ticks."""
        with (self.run_dir / "ticks.jsonl").open("w", encoding="utf-8") as stream:
            for record in records:
                stream.write(record.model_dump_json() + "\n")

    def save_text(self, name: str, text: str) -> None:
        """Save text."""
        (self.run_dir / name).write_text(text.rstrip() + "\n", encoding="utf-8")

    def complete_stage(self, stage: str) -> None:
        """Mark stage."""
        self.metadata["completed_stages"].append(stage)
        self._metadata()

    def complete(self, narrator: str, narrative_error: str | None) -> None:
        """Mark the requested value."""
        self.metadata.update(status="completed", narrator=narrator, narrative_error=narrative_error)
        self._metadata()

    def record_audio_failure(self) -> None:
        """Record a non-fatal narration failure."""
        self.metadata.update(
            audio_status="failed",
            audio_error="AUDIO_GENERATION_FAILED",
        )
        self._metadata()

    def fail(self, error: str) -> None:
        """Mark the requested value."""
        self.metadata.update(status="failed", error=error)
        self._metadata()

    def _metadata(self) -> None:
        """Handle the metadata operation for RunRepository."""
        self.metadata["updated_at"] = datetime.now(UTC).isoformat()
        (self.run_dir / "metadata.json").write_text(
            json.dumps(self.metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def result_row(result: SimulationResult, agents: int) -> dict:
    """Handle the result row operation for component."""
    return {
        "seed": result.seed,
        "agents": agents,
        "success": result.success,
        "ticks": result.ticks,
        "puzzles_solved": len(result.solved_puzzles),
        "messages": result.metrics.messages_sent,
        "blocked_time": result.metrics.blocked_time,
        "invalid_actions": result.metrics.invalid_actions,
        "distance": sum(a.distance for a in result.metrics.agents.values()),
        "replans": sum(a.replans for a in result.metrics.agents.values()),
    }


def _csv_text(rows: list[dict]) -> str:
    """Render rows as CSV text using the first row for the field order."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _batch_summary(rows: list[dict]) -> list[dict]:
    """Aggregate escape rate and average ticks per agent count."""
    summary = []
    for count in sorted({row["agents"] for row in rows}):
        subset = [row for row in rows if row["agents"] == count]
        escaped = [row for row in subset if row["success"]]
        summary.append(
            {
                "agents": count,
                "runs": len(subset),
                "escape_rate": len(escaped) / len(subset),
                "average_ticks": (
                    sum(row["ticks"] for row in escaped) / len(escaped) if escaped else ""
                ),
            }
        )
    return summary


def save_batch(root: Path, rows: list[dict], config: dict | None = None) -> Path:
    """Persist one batch experiment with the configuration needed to repeat it."""
    if not rows:
        raise ValueError("un lote sin ejecuciones no se puede guardar")
    now = datetime.now(UTC)
    # Second resolution used to collide silently under exist_ok=True, overwriting the CSVs of
    # the previous batch; runs have always used the anti-collision suffix instead.
    directory = _timestamped_directory(root / "experiments", now.strftime("%Y%m%d-%H%M%S"))
    atomic_write_text(directory / "runs.csv", _csv_text(rows))
    atomic_write_text(directory / "summary.csv", _csv_text(_batch_summary(rows)))
    atomic_write_json(
        directory / "experiment.json",
        {
            "experiment_id": directory.name,
            "created_at": now.isoformat(),
            "package_version": _package_version(),
            "runs": len(rows),
            **(config or {}),
        },
    )
    return directory
