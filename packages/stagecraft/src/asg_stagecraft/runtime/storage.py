"""Atomic persistence, manifest hashing, and incremental checkpoints."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from asg_core import artifact_json, atomic_write_text, create_unique_directory, slugify
from pydantic import BaseModel

from ..formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from ..schemas import ErrorReport, GeneratorVersionArtifact, LLMUsageRecord, RunMetadata
from ..version import PIPELINE_VERSION
from .errors import ASGError


class ArtifactRepository:
    """Represent ArtifactRepository data and behavior."""

    def __init__(
        self,
        output_root: Path,
        model: str,
        title: str,
        *,
        on_artifact: Callable[[str, bool], None] | None = None,
        story_format: StoryFormat = StoryFormat.NARRATIVE,
        script_method: ScriptMethod | None = None,
        narrative_voice: NarrativeVoice | None = None,
        actor_memory: ActorMemory | None = None,
        stage_model: str | None = None,
    ) -> None:
        """Initialize the ArtifactRepository instance."""
        now = datetime.now(UTC)
        base = f"{now.strftime('%Y%m%d-%H%M%S')}-{slugify(title, fallback='historia')}"
        run_dir = create_unique_directory(output_root, base)
        self.run_dir = run_dir
        self.on_artifact = on_artifact
        self.metadata = RunMetadata(
            run_id=run_dir.name,
            model=model,
            created_at=now,
            updated_at=now,
            status="running",
            pipeline_version=PIPELINE_VERSION,
            story_format=story_format,
            script_method=script_method,
            narrative_voice=narrative_voice,
            actor_memory=actor_memory,
            stage_model=stage_model,
        )
        self.manifest: dict = {
            "pipeline_version": PIPELINE_VERSION,
            "run_id": run_dir.name,
            "completed_stages": [],
            "artifacts": {},
        }
        # The sha256 state and size of every line-delimited artifact this process appends to.
        self._running_hashes: dict[str, list] = {}
        self._write_metadata()
        self._write_manifest()
        self.save_json("generator_version.json", GeneratorVersionArtifact())

    def _record(self, filename: str, content: str) -> None:
        """Handle the record operation for ArtifactRepository."""
        if filename in {"pipeline_manifest.json"}:
            return
        self.manifest["artifacts"][filename.replace("\\", "/")] = {
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "bytes": len(content.encode("utf-8")),
        }
        self._write_manifest()

    def save_json(self, filename: str, value: BaseModel) -> None:
        """Save json."""
        self.save_data(filename, value.model_dump(mode="json"))

    def save_data(self, filename: str, value) -> None:
        """Save data."""
        content = artifact_json(value)
        destination = self.run_dir / filename
        created = not destination.exists()
        atomic_write_text(destination, content)
        self._record(filename, content)
        if self.on_artifact:
            self.on_artifact(filename.replace("\\", "/"), created)

    def save_text(self, filename: str, value: str) -> None:
        """Save text."""
        content = value.rstrip() + "\n"
        destination = self.run_dir / filename
        created = not destination.exists()
        atomic_write_text(destination, content)
        self._record(filename, content)
        if self.on_artifact:
            self.on_artifact(filename.replace("\\", "/"), created)

    def register_existing(self, filename: str) -> None:
        """Register an existing binary or externally written artifact."""
        path = self.run_dir / filename
        content = path.read_bytes()
        normalized = filename.replace("\\", "/")
        self.manifest["artifacts"][normalized] = {
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
        self._write_manifest()
        if self.on_artifact:
            self.on_artifact(normalized, True)

    def append_llm_call(self, record: LLMUsageRecord) -> None:
        """Append one model call to llm_calls.jsonl, keeping it manifest-tracked."""
        self.append_jsonl("llm_calls.jsonl", record)

    def append_jsonl(self, filename: str, value: BaseModel | dict) -> None:
        """Append one JSON record to a line-delimited artifact, keeping it manifest-tracked.

        Written turn by turn by the performance and call by call by the provider, so the line is
        appended and folded into a running hash for the manifest; the file is read at most once,
        when this process first touches it. Before 7.2 every line reread and rewrote the whole
        file, quadratic in the length of the run.
        """
        path = self.run_dir / filename
        normalized = filename.replace("\\", "/")
        created = not path.exists()
        data = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        encoded = (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")
        running = self._running_hashes.get(normalized)
        if running is None:
            existing = b"" if created else path.read_bytes()
            running = self._running_hashes[normalized] = [hashlib.sha256(existing), len(existing)]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        running[0].update(encoded)
        running[1] += len(encoded)
        self.manifest["artifacts"][normalized] = {
            "sha256": running[0].hexdigest(),
            "bytes": running[1],
        }
        self._write_manifest()
        if self.on_artifact:
            self.on_artifact(normalized, created)

    def complete_stage(self, stage: str) -> None:
        """Mark stage."""
        if stage not in self.metadata.completed_stages:
            self.metadata.completed_stages.append(stage)
        if stage not in self.manifest["completed_stages"]:
            self.manifest["completed_stages"].append(stage)
        self.metadata.updated_at = datetime.now(UTC)
        self._write_metadata()
        self._write_manifest()

    def complete(self) -> None:
        """Mark the requested value."""
        self.metadata.status = "completed"
        self.metadata.updated_at = datetime.now(UTC)
        self._write_metadata()

    def add_warning(self, warning: str) -> None:
        """Add warning."""
        if warning not in self.metadata.warnings:
            self.metadata.warnings.append(warning)
        self.metadata.updated_at = datetime.now(UTC)
        self._write_metadata()

    def fail(self, error: Exception, *, stage: str | None = None) -> None:
        """Record a failed run under the pipeline stage the caller observed.

        An error's own stage names the component that raised it - "provider" for every Gemini
        failure - so it is kept in details.component, and the report says where the run died.
        Before 7.2 the component won, and every quota failure read as stage "provider".
        """
        if isinstance(error, ASGError):
            error.run_id = self.metadata.run_id
            failed_stage = stage or error.stage
            details = dict(error.details)
            if error.stage != failed_stage:
                details.setdefault("component", error.stage)
            self.metadata.error = error.summary
            self.metadata.error_code = error.code
            self.metadata.error_stage = failed_stage
            report = ErrorReport(
                code=error.code,
                stage=failed_stage,
                run_id=self.metadata.run_id,
                summary=error.summary,
                details=details,
                recommendations=error.recommendations,
            )
        else:
            failed_stage = stage or "unknown"
            self.metadata.error = "Ocurrió un error interno inesperado."
            self.metadata.error_code = "UNEXPECTED_ERROR"
            self.metadata.error_stage = failed_stage
            report = ErrorReport(
                code="UNEXPECTED_ERROR",
                stage=failed_stage,
                run_id=self.metadata.run_id,
                summary="Ocurrió un error interno inesperado.",
                details={"exception_type": type(error).__name__},
                recommendations=["Consulta el registro local y vuelve a intentarlo."],
            )
        self.save_json("error_report.json", report)
        self.metadata.status = "failed"
        self.metadata.updated_at = datetime.now(UTC)
        self._write_metadata()

    def _write_metadata(self) -> None:
        """Handle the write metadata operation for ArtifactRepository."""
        content = artifact_json(self.metadata.model_dump(mode="json"))
        atomic_write_text(self.run_dir / "metadata.json", content)
        if hasattr(self, "manifest"):
            self._record("metadata.json", content)

    def _write_manifest(self) -> None:
        """Handle the write manifest operation for ArtifactRepository."""
        content = artifact_json(self.manifest)
        atomic_write_text(self.run_dir / "pipeline_manifest.json", content)
