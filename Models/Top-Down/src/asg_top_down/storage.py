"""Persistencia incremental y segura de artefactos."""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .errors import ASGError
from .schemas import ErrorReport, RunMetadata


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
            pipeline_version="3.3",
        )
        self._write_metadata()

    @classmethod
    def open_existing(cls, run_dir: Path) -> "ArtifactRepository":
        instance = cls.__new__(cls)
        instance.run_dir = Path(run_dir)
        instance.metadata = RunMetadata.model_validate_json(
            (instance.run_dir / "metadata.json").read_text(encoding="utf-8")
        )
        instance.metadata.status = "running"
        instance.metadata.error = None
        instance.metadata.error_code = None
        instance.metadata.error_stage = None
        instance._write_metadata()
        return instance

    def save_json(self, filename: str, value: BaseModel) -> None:
        self.save_data(filename, value.model_dump(mode="json"))

    def save_data(self, filename: str, value) -> None:
        content = json.dumps(value, ensure_ascii=False, indent=2)
        destination = self.run_dir / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content + "\n", encoding="utf-8")

    def save_text(self, filename: str, value: str) -> None:
        destination = self.run_dir / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(value.rstrip() + "\n", encoding="utf-8")

    def complete_stage(self, stage: str) -> None:
        if stage not in self.metadata.completed_stages:
            self.metadata.completed_stages.append(stage)
        self.metadata.updated_at = datetime.now(timezone.utc)
        self._write_metadata()

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
            self.save_json("error_report.json", ErrorReport(
                code=error.code, stage=error.stage, run_id=self.metadata.run_id,
                summary=error.summary, details=error.details,
                recommendations=error.recommendations,
            ))
        else:
            self.metadata.error = "Ocurrió un error interno inesperado."
            self.metadata.error_code = "UNEXPECTED_ERROR"
            self.metadata.error_stage = "unknown"
            self.save_json("error_report.json", ErrorReport(
                code="UNEXPECTED_ERROR", stage="unknown", run_id=self.metadata.run_id,
                summary="Ocurrió un error interno inesperado.",
                details={"exception_type": type(error).__name__},
                recommendations=["Consulta el registro local y vuelve a intentarlo."],
            ))
        self.metadata.status = "failed"
        self.metadata.updated_at = datetime.now(timezone.utc)
        self._write_metadata()

    def _write_metadata(self) -> None:
        content = json.dumps(
            self.metadata.model_dump(mode="json"), ensure_ascii=False, indent=2
        )
        (self.run_dir / "metadata.json").write_text(content + "\n", encoding="utf-8")
