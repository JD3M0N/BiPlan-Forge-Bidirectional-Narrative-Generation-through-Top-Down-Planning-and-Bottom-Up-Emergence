"""Persistencia incremental y segura de artefactos."""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .schemas import RunMetadata


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")[:60] or "historia"


class ArtifactRepository:
    def __init__(self, output_root: Path, model: str, title: str) -> None:
        now = datetime.now(timezone.utc)
        base = f"{now.strftime('%Y%m%d-%H%M%S')}-{slugify(title)}"
        run_dir = output_root / base
        suffix = 2
        while run_dir.exists():
            run_dir = output_root / f"{base}-{suffix}"
            suffix += 1
        run_dir.mkdir(parents=True, exist_ok=False)
        self.run_dir = run_dir
        self.metadata = RunMetadata(
            run_id=run_dir.name,
            model=model,
            created_at=now,
            updated_at=now,
            status="running",
        )
        self._write_metadata()

    def save_json(self, filename: str, value: BaseModel) -> None:
        content = json.dumps(
            value.model_dump(mode="json"), ensure_ascii=False, indent=2
        )
        (self.run_dir / filename).write_text(content + "\n", encoding="utf-8")

    def save_text(self, filename: str, value: str) -> None:
        (self.run_dir / filename).write_text(value.rstrip() + "\n", encoding="utf-8")

    def complete_stage(self, stage: str) -> None:
        self.metadata.completed_stages.append(stage)
        self.metadata.updated_at = datetime.now(timezone.utc)
        self._write_metadata()

    def complete(self) -> None:
        self.metadata.status = "completed"
        self.metadata.updated_at = datetime.now(timezone.utc)
        self._write_metadata()

    def fail(self, error: str) -> None:
        self.metadata.status = "failed"
        self.metadata.error = error
        self.metadata.updated_at = datetime.now(timezone.utc)
        self._write_metadata()

    def _write_metadata(self) -> None:
        content = json.dumps(
            self.metadata.model_dump(mode="json"), ensure_ascii=False, indent=2
        )
        (self.run_dir / "metadata.json").write_text(content + "\n", encoding="utf-8")

