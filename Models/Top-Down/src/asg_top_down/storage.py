"""Atomic persistence, manifest hashing, and incremental checkpoints."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from .errors import ASGError
from .schemas import ErrorReport, LLMUsageRecord, RunMetadata


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")[:60] or "historia"


class ArtifactRepository:
    def __init__(self, output_root: Path, model: str, title: str, *,
                 on_artifact: Callable[[str, bool], None] | None = None) -> None:
        now = datetime.now(timezone.utc)
        base = f"{now.strftime('%Y%m%d-%H%M%S')}-{slugify(title)}"
        run_dir = output_root / base
        suffix = 2
        while run_dir.exists():
            run_dir = output_root / f"{base}-{suffix}"
            suffix += 1
        run_dir.mkdir(parents=True, exist_ok=False)
        self.run_dir = run_dir
        self.on_artifact = on_artifact
        self.metadata = RunMetadata(
            run_id=run_dir.name, model=model, created_at=now, updated_at=now,
            status="running", pipeline_version="5.0",
        )
        self.manifest: dict = {
            "pipeline_version": "5.0", "run_id": run_dir.name,
            "completed_stages": [], "artifacts": {},
        }
        self._write_metadata()
        self._write_manifest()

    @staticmethod
    def _atomic_write(destination: Path, content: str) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _record(self, filename: str, content: str) -> None:
        if filename in {"pipeline_manifest.json"}:
            return
        self.manifest["artifacts"][filename.replace("\\", "/")] = {
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "bytes": len(content.encode("utf-8")),
        }
        self._write_manifest()

    def save_json(self, filename: str, value: BaseModel) -> None:
        self.save_data(filename, value.model_dump(mode="json"))

    def save_data(self, filename: str, value) -> None:
        content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        destination = self.run_dir / filename
        created = not destination.exists()
        self._atomic_write(destination, content)
        self._record(filename, content)
        if self.on_artifact:
            self.on_artifact(filename.replace("\\", "/"), created)

    def save_text(self, filename: str, value: str) -> None:
        content = value.rstrip() + "\n"
        destination = self.run_dir / filename
        created = not destination.exists()
        self._atomic_write(destination, content)
        self._record(filename, content)
        if self.on_artifact:
            self.on_artifact(filename.replace("\\", "/"), created)

    def append_llm_call(self, record: LLMUsageRecord) -> None:
        path = self.run_dir / "llm_calls.jsonl"
        created = not path.exists()
        existing = path.read_text(encoding="utf-8") if not created else ""
        line = json.dumps(record.model_dump(mode="json"), ensure_ascii=False) + "\n"
        self._atomic_write(path, existing + line)
        self._record("llm_calls.jsonl", existing + line)
        if self.on_artifact:
            self.on_artifact("llm_calls.jsonl", created)

    def complete_stage(self, stage: str) -> None:
        if stage not in self.metadata.completed_stages:
            self.metadata.completed_stages.append(stage)
        if stage not in self.manifest["completed_stages"]:
            self.manifest["completed_stages"].append(stage)
        self.metadata.updated_at = datetime.now(timezone.utc)
        self._write_metadata()
        self._write_manifest()

    def complete(self) -> None:
        self.metadata.status = "completed"
        self.metadata.updated_at = datetime.now(timezone.utc)
        self._write_metadata()

    def add_warning(self, warning: str) -> None:
        if warning not in self.metadata.warnings:
            self.metadata.warnings.append(warning)
        self.metadata.updated_at = datetime.now(timezone.utc)
        self._write_metadata()

    def fail(self, error: Exception) -> None:
        if isinstance(error, ASGError):
            error.run_id = self.metadata.run_id
            self.metadata.error = error.summary
            self.metadata.error_code = error.code
            self.metadata.error_stage = error.stage
            report = ErrorReport(
                code=error.code, stage=error.stage, run_id=self.metadata.run_id,
                summary=error.summary, details=error.details,
                recommendations=error.recommendations,
            )
        else:
            self.metadata.error = "Ocurrió un error interno inesperado."
            self.metadata.error_code = "UNEXPECTED_ERROR"
            self.metadata.error_stage = "unknown"
            report = ErrorReport(
                code="UNEXPECTED_ERROR", stage="unknown", run_id=self.metadata.run_id,
                summary="Ocurrió un error interno inesperado.",
                details={"exception_type": type(error).__name__},
                recommendations=["Consulta el registro local y vuelve a intentarlo."],
            )
        self.save_json("error_report.json", report)
        self.metadata.status = "failed"
        self.metadata.updated_at = datetime.now(timezone.utc)
        self._write_metadata()

    def _write_metadata(self) -> None:
        content = json.dumps(self.metadata.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
        self._atomic_write(self.run_dir / "metadata.json", content)
        if hasattr(self, "manifest"):
            self._record("metadata.json", content)

    def _write_manifest(self) -> None:
        content = json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n"
        self._atomic_write(self.run_dir / "pipeline_manifest.json", content)
