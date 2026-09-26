"""Post-hoc LLM audit of one performed run: knowledge boundaries and narration fidelity.

Run by hand over a sample, never by the pipeline: it spends real quota and answers questions the
deterministic metrics can only approximate. It never modifies the run it reads - everything it
writes goes under ``<run>/audit/`` and carries the hash of the manifest it was computed against,
so an audit can always be told apart from the run it describes and re-run if the run changes.

Two judgements, from two different literatures:

- **Knowledge boundary**, one call per scene. The judge sees what each character's memory held
  when the scene opened and what they then said, and flags anything a character could not have
  known. This is the measurement that separates ``--actor-memory own`` from ``shared``, graded
  the way KBF and TimeChara grade point-in-time role-play.
- **Narration fidelity**, one call per chapter. The judge compares the prose against the log it
  was written from and flags invented events, contradictions and dropped beats, scored with
  CoSER's penalty scheme (100 - 5 x sum of severities).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..runtime.config import load_settings
from ..runtime.errors import ASGError, RunArtifactError
from ..runtime.provider import provider_from_settings

# CoSER scores a simulation by subtracting five points per severity point of every flaw found,
# which keeps one severe breach from hiding behind many clean scenes.
PENALTY_PER_SEVERITY = 5


class AuditFinding(BaseModel):
    """One thing the judge found wrong, with the evidence that shows it."""

    kind: Literal["knowledge_leak", "invented_event", "contradiction", "dropped_beat"]
    severity: int = Field(ge=1, le=5, description="1 for a trifle, 5 for a breach that ruins it.")
    character_id: str = Field(default="", description="Who committed it, when it is one character.")
    evidence: str = Field(min_length=1, description="Quote the turn or the sentence itself.")
    explanation: str = Field(min_length=1, description="In English: why this is wrong.")


class SceneAudit(BaseModel):
    """The judge's verdict on one performed scene."""

    findings: list[AuditFinding] = Field(default_factory=list)


class ChapterAudit(BaseModel):
    """The judge's verdict on one narrated chapter against its log."""

    findings: list[AuditFinding] = Field(default_factory=list)


def score(findings: list[AuditFinding]) -> float:
    """Turn findings into a 0-100 score, the way CoSER penalizes a simulation."""
    penalty = PENALTY_PER_SEVERITY * sum(item.severity for item in findings)
    return round(max(0.0, 100.0 - penalty), 2)


def audit_knowledge(provider, scene: dict, memories: str, transcript: str) -> SceneAudit:
    """Ask whether anyone in one scene spoke about something they could not know."""
    return provider.generate_structured(
        system_instruction=(
            "You are auditing an improvised performance for knowledge-boundary violations. Below "
            "is what each character's memory held when the scene opened, and then what they said "
            "and did. Flag every moment a character refers to, acts on, or reveals something "
            "their own memory does not contain and the scene has not yet shown them. Judge only "
            "what a character could know, never whether the scene is good. A character may guess, "
            "be wrong, or infer from what is in front of them: that is not a violation. Stating a "
            "fact they were never told is. Return an empty list when the scene is clean."
        ),
        prompt=(
            f"SCENE:\n{json.dumps(scene, ensure_ascii=False, indent=2)}"
            f"\n\nWHAT EACH CHARACTER KNEW WHEN THE SCENE OPENED:\n{memories}"
            f"\n\nWHAT THEY THEN SAID AND DID:\n{transcript}"
        ),
        schema=SceneAudit,
        profile="review",
    )


def audit_narration(provider, chapter_title: str, prose: str, log: str) -> ChapterAudit:
    """Ask whether one narrated chapter is faithful to the log it was written from."""
    return provider.generate_structured(
        system_instruction=(
            "You are auditing a chapter of prose against the performance log it was written from. "
            "The log is the record of what actually happened. Flag three things: an invented "
            "event the log does not contain, a statement that contradicts the log, and a beat the "
            "log contains that the prose drops entirely. Selecting, compressing and reordering "
            "within the chapter are the narrator's job and are not faults; rendering a recorded "
            "thought as interior narration is not a fault either. Return an empty list when the "
            "chapter is faithful."
        ),
        prompt=(f"CHAPTER: {chapter_title}\n\nPERFORMANCE LOG:\n{log}\n\nNARRATED PROSE:\n{prose}"),
        schema=ChapterAudit,
        profile="review",
    )


def manifest_hash(run_dir: Path) -> str:
    """Hash the run's manifest, so an audit can be matched to the exact run it described."""
    path = run_dir / "pipeline_manifest.json"
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _load(path: Path) -> dict:
    """Read one JSON artifact of the run being audited."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunArtifactError(f"No se pudo leer {path.name} en {path.parent}.") from exc


def _memories_at(run_dir: Path, character_ids: list[str], scene_number: int) -> str:
    """Render what each character's memory held before one scene began."""
    blocks = []
    for character_id in character_ids:
        path = run_dir / "memory" / character_id / "records.json"
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        earlier = [item for item in records if item.get("scene_number", 0) < scene_number]
        lines = "\n".join(f"  - {item['text']}" for item in earlier) or "  (nothing yet)"
        blocks.append(f"{character_id}:\n{lines}")
    return "\n\n".join(blocks)


def _transcript(run_dir: Path, scene_id: str) -> str:
    """Read one scene's human-readable transcript."""
    path = run_dir / "stage" / scene_id / "transcript.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def audit_run(run_dir: Path, provider, *, scenes_only: bool = False) -> dict:
    """Audit one performed run and return the report written under audit/."""
    performance = _load(run_dir / "performance.json")
    narration = _load(run_dir / "narration.json")
    scene_reports = []
    for scene in performance.get("scenes", []):
        character_ids = sorted({turn["actor_id"] for turn in scene.get("turns", [])})
        verdict = audit_knowledge(
            provider,
            {"scene_id": scene["scene_id"], "chapter_id": scene["chapter_id"]},
            _memories_at(run_dir, character_ids, scene.get("number", 1)),
            _transcript(run_dir, scene["scene_id"]),
        )
        scene_reports.append(
            {
                "scene_id": scene["scene_id"],
                "score": score(verdict.findings),
                "findings": [item.model_dump(mode="json") for item in verdict.findings],
            }
        )

    chapter_reports = []
    if not scenes_only:
        by_chapter: dict[str, list[dict]] = {}
        for scene in performance.get("scenes", []):
            by_chapter.setdefault(scene["chapter_id"], []).append(scene)
        for index, chapter in enumerate(narration.get("chapters", []), 1):
            prose_path = run_dir / "narration" / f"chapter-{chapter['chapter_index']:03d}.md"
            log = "\n\n".join(
                _transcript(run_dir, scene["scene_id"])
                for scene in by_chapter.get(chapter["chapter_id"], [])
            )
            try:
                prose = prose_path.read_text(encoding="utf-8")
            except OSError:
                continue
            verdict = audit_narration(provider, f"Capitulo {index}", prose, log)
            chapter_reports.append(
                {
                    "chapter_id": chapter["chapter_id"],
                    "score": score(verdict.findings),
                    "findings": [item.model_dump(mode="json") for item in verdict.findings],
                }
            )

    leaks = [
        finding
        for report in scene_reports
        for finding in report["findings"]
        if finding["kind"] == "knowledge_leak"
    ]
    return {
        "contract_version": "1",
        "audited_at": datetime.now(UTC).isoformat(),
        "model": provider.model_name,
        "source_manifest_sha256": manifest_hash(run_dir),
        "actor_memory": performance.get("settings", {}).get("actor_memory"),
        "narrative_voice": narration.get("narrative_voice"),
        "knowledge_leaks": len(leaks),
        "knowledge_score": (
            round(sum(item["score"] for item in scene_reports) / len(scene_reports), 2)
            if scene_reports
            else 0.0
        ),
        "narration_score": (
            round(sum(item["score"] for item in chapter_reports) / len(chapter_reports), 2)
            if chapter_reports
            else 0.0
        ),
        "scenes": scene_reports,
        "chapters": chapter_reports,
    }


def parser() -> argparse.ArgumentParser:
    """Build the stage-audit command-line parser."""
    result = argparse.ArgumentParser(
        description="Audita con un LLM la frontera de conocimiento y la fidelidad de una función"
    )
    result.add_argument("run", help="Directorio de la ejecución simulada a auditar")
    result.add_argument(
        "--model",
        help="Modelo de Gemini a usar como juez, en lugar del configurado en .env",
    )
    result.add_argument(
        "--scenes-only",
        action="store_true",
        help="Audita solo la frontera de conocimiento y salta la fidelidad de la narración",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the stage-audit entry point."""
    from dataclasses import replace

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    run_dir = Path(args.run)
    if not (run_dir / "performance.json").is_file():
        print(f"Error: {run_dir} no contiene una función representada.", file=sys.stderr)
        return 2
    try:
        settings = load_settings()
        if args.model:
            settings = replace(settings, model=args.model)
        provider = provider_from_settings(settings)
        print(f"Auditando {run_dir.name} con {settings.model}...")
        report = audit_run(run_dir, provider, scenes_only=args.scenes_only)
    except (ASGError, KeyboardInterrupt) as exc:
        message = exc.public_message() if isinstance(exc, ASGError) else "operación cancelada"
        print(f"\nError: {message}", file=sys.stderr)
        return 1

    destination = run_dir / "audit" / "audit.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nFugas de frontera de conocimiento: {report['knowledge_leaks']}")
    print(f"Puntuación de conocimiento: {report['knowledge_score']}")
    print(f"Puntuación de fidelidad de la narración: {report['narration_score']}")
    print(f"Informe escrito en {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
