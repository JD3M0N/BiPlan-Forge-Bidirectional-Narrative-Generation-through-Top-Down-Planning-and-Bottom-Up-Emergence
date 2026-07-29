"""Persistencia auditable de una simulación y de experimentos batch."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel

from .contracts import RoomConfig, SimulationResult, TickRecord


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")[:60] or "escape-room"


class RunRepository:
    def __init__(self, root: Path, room_name: str, model: str) -> None:
        now = datetime.now(timezone.utc)
        base = f"{now.strftime('%Y%m%d-%H%M%S')}-{slugify(room_name)}"
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
        data = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        (self.run_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def save_ticks(self, records: Iterable[TickRecord]) -> None:
        with (self.run_dir / "ticks.jsonl").open("w", encoding="utf-8") as stream:
            for record in records:
                stream.write(record.model_dump_json() + "\n")

    def save_text(self, name: str, text: str) -> None:
        (self.run_dir / name).write_text(text.rstrip() + "\n", encoding="utf-8")

    def complete_stage(self, stage: str) -> None:
        self.metadata["completed_stages"].append(stage)
        self._metadata()

    def complete(self, narrator: str, narrative_error: str | None) -> None:
        self.metadata.update(
            status="completed", narrator=narrator, narrative_error=narrative_error
        )
        self._metadata()

    def fail(self, error: str) -> None:
        self.metadata.update(status="failed", error=error)
        self._metadata()

    def _metadata(self) -> None:
        self.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        (self.run_dir / "metadata.json").write_text(
            json.dumps(self.metadata, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def result_row(result: SimulationResult, agents: int) -> dict:
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
    directory = root / "experiments" / datetime.now(timezone.utc).strftime(
        "%Y%m%d-%H%M%S"
    )
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
                    sum(row["ticks"] for row in escaped) / len(escaped)
                    if escaped
                    else ""
                ),
            }
        )
    with (directory / "summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    return directory

