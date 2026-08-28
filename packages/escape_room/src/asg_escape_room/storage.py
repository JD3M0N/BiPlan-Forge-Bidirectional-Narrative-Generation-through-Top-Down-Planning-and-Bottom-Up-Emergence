"""Auditable persistence for simulations and batch experiments."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from asg_core import slugify
from pydantic import BaseModel

from .contracts import SimulationResult, TickRecord


class RunRepository:
    """Represent RunRepository data and behavior."""

    def __init__(self, root: Path, room_name: str, model: str) -> None:
        """Initialize the RunRepository instance."""
        now = datetime.now(UTC)
        base = f"{now.strftime('%Y%m%d-%H%M%S')}-{slugify(room_name, fallback='escape-room')}"
        self.run_dir = root / base
        suffix = 2
        while self.run_dir.exists():
            self.run_dir = root / f"{base}-{suffix}"
            suffix += 1
        self.run_dir.mkdir(parents=True)
        self.metadata = {
            "run_id": self.run_dir.name,
            "model": model,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "status": "running",
            "completed_stages": [],
            "narrator": None,
            "narrative_error": None,
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


def save_batch(root: Path, rows: list[dict]) -> Path:
    """Save batch."""
    directory = root / "experiments" / datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    directory.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with (directory / "runs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
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
    with (directory / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    return directory
