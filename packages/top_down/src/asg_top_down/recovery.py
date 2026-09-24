"""Explicit transitions for runs the pipeline abandoned before closing them.

A run is created with status "running" and only reaches "completed" or "failed" from inside
StoryPipeline.execute. A process killed mid-run used to leave that status behind forever, and
StoryRun refuses to open anything but a completed run, so finished stories became unreachable.
These transitions close or discard such a run without touching a single story artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from asg_core import atomic_write_text, stories_path

from .errors import RunArtifactError
from .schemas import ErrorReport
from .version import SUPPORTED_PIPELINE_VERSIONS

RECOVERED_CODE = "RUN_RECOVERED"
DISCARDED_CODE = "RUN_INTERRUPTED"
DISCARDED_SUMMARY = "La generación se interrumpió antes de terminar."


@dataclass(frozen=True)
class StalledRun:
    """One run left in "running", with the verdict on whether its story can be rescued."""

    run_dir: Path
    pipeline_version: str | None
    has_story: bool

    @property
    def recoverable(self) -> bool:
        """Report whether closing this run would make it openable as a StoryRun."""
        return self.has_story and self.pipeline_version in SUPPORTED_PIPELINE_VERSIONS

    @property
    def reason(self) -> str:
        """Explain in Spanish why this run can or cannot be closed."""
        if self.recoverable:
            return "recuperable: tiene story.md y una version de pipeline soportada"
        if not self.has_story:
            return "descartable: no llego a escribir story.md"
        return f"descartable: version de pipeline no soportada ({self.pipeline_version})"


def read_metadata(run_dir: Path) -> dict:
    """Read one run's metadata, refusing anything that is not a readable JSON object."""
    path = Path(run_dir) / "metadata.json"
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunArtifactError(f"No se encontró metadata.json en {run_dir}.") from exc
    except json.JSONDecodeError as exc:
        raise RunArtifactError(f"metadata.json en {run_dir} no es JSON válido.") from exc
    if not isinstance(metadata, dict):
        raise RunArtifactError(f"metadata.json en {run_dir} no describe una ejecución.")
    return metadata


def stalled_runs(root: Path | str) -> list[StalledRun]:
    """Collect every run under root that is still marked as running, oldest first."""
    directory = Path(root)
    found = []
    for run_dir in sorted(directory.iterdir()) if directory.is_dir() else []:
        if not (run_dir / "metadata.json").is_file():
            continue
        try:
            metadata = read_metadata(run_dir)
        except RunArtifactError:
            continue
        if metadata.get("status") != "running":
            continue
        found.append(_describe(run_dir, metadata))
    return found


def close_stalled_run(run_dir: Path | str) -> Path:
    """Close a stalled run whose story survived, leaving an audit line in its warnings."""
    run_dir = Path(run_dir)
    metadata = _running_metadata(run_dir)
    stalled = _describe(run_dir, metadata)
    if not stalled.recoverable:
        raise RunArtifactError(f"{run_dir.name} no se puede cerrar: {stalled.reason}.")
    warnings = list(metadata.get("warnings") or [])
    warnings.append(
        f"[{RECOVERED_CODE}] Ejecución cerrada a mano el {_today()}: el pipeline se interrumpió "
        f"tras la etapa {_last_stage(metadata)} y nunca la marcó como terminada."
    )
    metadata["warnings"] = warnings
    metadata["status"] = "completed"
    _write_metadata(run_dir, metadata)
    return run_dir


def discard_stalled_run(run_dir: Path | str) -> Path:
    """Mark a stalled run as failed, keeping every artifact it managed to write."""
    run_dir = Path(run_dir)
    metadata = _running_metadata(run_dir)
    stage = _last_stage(metadata)
    metadata["status"] = "failed"
    metadata["error"] = DISCARDED_SUMMARY
    metadata["error_code"] = DISCARDED_CODE
    metadata["error_stage"] = stage
    report = ErrorReport(
        code=DISCARDED_CODE,
        stage=stage,
        run_id=str(metadata.get("run_id") or run_dir.name),
        summary=DISCARDED_SUMMARY,
        details={"discarded_on": _today()},
        recommendations=["Vuelve a lanzar la generación: esta ejecución quedó incompleta."],
    )
    _write_json(run_dir, "error_report.json", report.model_dump(mode="json"))
    _write_metadata(run_dir, metadata)
    return run_dir


def _describe(run_dir: Path, metadata: dict) -> StalledRun:
    """Pair one run directory with the two facts that decide whether it can be closed."""
    return StalledRun(
        run_dir=run_dir,
        pipeline_version=metadata.get("pipeline_version"),
        has_story=(run_dir / "story.md").is_file(),
    )


def _running_metadata(run_dir: Path) -> dict:
    """Read metadata for a transition, refusing a run that is not stalled in running."""
    metadata = read_metadata(run_dir)
    if metadata.get("status") != "running":
        raise RunArtifactError(
            f"{run_dir.name} no está en running, sino en {metadata.get('status')!r}."
        )
    return metadata


def _today() -> str:
    """Render the current UTC date the way run identifiers spell it."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _last_stage(metadata: dict) -> str:
    """Name the last stage the run finished, or "unknown" when it reported none."""
    stages = metadata.get("completed_stages") or []
    return str(stages[-1]) if stages else "unknown"


def _write_metadata(run_dir: Path, metadata: dict) -> None:
    """Rewrite metadata atomically and refresh the hash the manifest keeps of it."""
    content = _write_json(run_dir, "metadata.json", metadata)
    manifest_path = run_dir / "pipeline_manifest.json"
    if not manifest_path.is_file():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    artifacts = manifest.get("artifacts") if isinstance(manifest, dict) else None
    # Only refresh an entry the manifest already tracked: inventing one would claim the run
    # hashed an artifact it never did.
    if not isinstance(artifacts, dict) or "metadata.json" not in artifacts:
        return
    encoded = content.encode("utf-8")
    artifacts["metadata.json"] = {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
    }
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def _write_json(run_dir: Path, filename: str, value: dict) -> str:
    """Write one JSON artifact the way ArtifactRepository does, and return its text."""
    content = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(run_dir / filename, content)
    return content


def parser() -> argparse.ArgumentParser:
    """Build the stalled-run recovery command-line parser."""
    result = argparse.ArgumentParser(
        description="Cierra o descarta las ejecuciones Top-Down que quedaron en running"
    )
    result.add_argument(
        "--stories",
        help="Directorio de ejecuciones Top-Down; por defecto el Stories/Top-Down del proyecto",
    )
    result.add_argument(
        "--close",
        action="store_true",
        help="Cierra como completed las ejecuciones recuperables",
    )
    result.add_argument(
        "--discard",
        action="store_true",
        help="Marca como failed las ejecuciones que no se pueden recuperar",
    )
    result.add_argument(
        "--all",
        action="store_true",
        help="Equivale a --close y --discard a la vez",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the stalled-run recovery entry point."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    root = Path(args.stories) if args.stories else stories_path("Top-Down")
    close = args.close or args.all
    discard = args.discard or args.all
    runs = stalled_runs(root)
    if not runs:
        print(f"No hay ejecuciones en running bajo {root}.")
        return 0
    print(f"Ejecuciones en running bajo {root}: {len(runs)}\n")
    for run in runs:
        action = "sin cambios"
        if run.recoverable and close:
            close_stalled_run(run.run_dir)
            action = "cerrada como completed"
        elif not run.recoverable and discard:
            discard_stalled_run(run.run_dir)
            action = "descartada como failed"
        print(f"  {run.run_dir.name}\n    {run.reason}\n    {action}")
    if not (close or discard):
        print("\nNo se escribió nada. Usa --close, --discard o --all para aplicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
