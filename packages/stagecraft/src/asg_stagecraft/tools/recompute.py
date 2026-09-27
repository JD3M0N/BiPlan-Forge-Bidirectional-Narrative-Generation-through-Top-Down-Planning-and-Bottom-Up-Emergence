"""Recompute a performed run's measurements from its own logs, never touching the original.

A run's simulation_metrics.json is written once, with whatever the metrics module measured at
the time, so a run older than a measurement cannot report it: the 7.0 runs lack every figure 7.1
added, and the design doc once quoted those figures recomputed by hand. This command rebuilds
what the current code measures from the artifacts the run already has on disk, and writes it
beside the original as simulation_metrics.recomputed.json. Like audit-stage-run it never modifies
what it reads; unlike it, it spends no quota.

Two figures cannot be rebuilt from the logs. The emotion each reflection named was not persisted
before 7.2, so emotions are copied from the original measurements when they exist. And a cast
bible written under an earlier gate contract cannot be read by the current one, so its
gates_known_by_discoverer comes back as null - not measured - rather than as a clean zero.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asg_core import atomic_write_json, use_utf8_output
from pydantic import ValidationError

from ..formats import NarrativeVoice
from ..runtime.errors import ASGError, RunArtifactError
from ..stage.memory import CharacterMemory
from ..stage.metrics import simulation_metrics
from ..stage.schemas import CastBible, MemoryRecord, MemoryRetrieval, PerformanceArtifact

OUTPUT_NAME = "simulation_metrics.recomputed.json"


def _read(path: Path):
    """Read one JSON artifact of the run, naming it when it cannot be read."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunArtifactError(f"No se pudo leer {path.name} en {path.parent}.") from exc


def _optional(path: Path):
    """Read one JSON artifact the run may lack, or None when it is absent."""
    return _read(path) if path.is_file() else None


def _memories(run_dir: Path) -> dict[str, CharacterMemory]:
    """Rebuild each character's memory stream from the records and retrievals it logged."""
    memories: dict[str, CharacterMemory] = {}
    for folder in sorted(path for path in (run_dir / "memory").glob("*") if path.is_dir()):
        memory = CharacterMemory(folder.name)
        memory.records = [
            MemoryRecord.model_validate(item) for item in _read(folder / "records.json")
        ]
        memory.retrievals = [
            MemoryRetrieval.model_validate(item)
            for item in (_optional(folder / "retrievals.json") or [])
        ]
        memories[folder.name] = memory
    return memories


def _scripted_lines(run_dir: Path) -> dict[str, list[str]]:
    """Read the script's reference lines per scene from each brief the performance kept."""
    lines: dict[str, list[str]] = {}
    for path in sorted((run_dir / "stage").glob("*/brief.json")):
        brief = _read(path)
        lines[brief.get("scene_id", path.parent.name)] = list(brief.get("scripted_lines") or [])
    return lines


def _recorded_emotions(run_dir: Path) -> dict[str, list[str]]:
    """Copy the emotions the run recorded itself: the logs alone cannot rebuild them."""
    recorded = _optional(run_dir / "simulation_metrics.json") or {}
    return {
        item["character_id"]: list(item.get("emotions") or [])
        for item in recorded.get("actor_metrics") or []
        if isinstance(item, dict) and item.get("character_id")
    }


def recompute(run_dir: Path) -> dict:
    """Measure one performed run again with the current code, from its artifacts alone."""
    performance = PerformanceArtifact.model_validate(_read(run_dir / "performance.json"))
    request = _read(run_dir / "request.json")
    narration = _optional(run_dir / "narration.json") or {}
    characters = _read(run_dir / "characters.json")
    names = {item["id"]: item["name"] for item in characters.get("characters", [])}
    try:
        bible_data = _optional(run_dir / "cast_bible.json")
        bible = CastBible.model_validate(bible_data) if bible_data else None
    except ValidationError:
        bible = None
    story_path = run_dir / "story.md"
    story = story_path.read_text(encoding="utf-8") if story_path.is_file() else ""
    fallbacks = sum(
        1 for chapter in narration.get("chapters") or [] if chapter.get("source") == "fallback"
    )
    metrics = simulation_metrics(
        profile=request["narrative_profile"],
        performance=performance,
        scripted_by_scene=_scripted_lines(run_dir),
        memories=_memories(run_dir),
        names=names,
        story=story,
        narration_fallbacks=fallbacks,
        bible=bible,
        emotions=_recorded_emotions(run_dir),
    )
    if narration.get("narrative_voice"):
        voice = NarrativeVoice(narration["narrative_voice"])
        metrics = metrics.model_copy(update={"narrative_voice": voice})
    data = metrics.model_dump(mode="json")
    if bible is None:
        data["gates_known_by_discoverer"] = None
    return data


def parser() -> argparse.ArgumentParser:
    """Build the recompute command-line parser."""
    result = argparse.ArgumentParser(
        description=(
            "Recalcula las métricas de una función representada desde sus propios logs, "
            "sin tocar el original"
        )
    )
    result.add_argument("run", help="Directorio de la ejecución simulada")
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the recompute entry point."""
    use_utf8_output()
    args = parser().parse_args(argv)
    run_dir = Path(args.run)
    if not (run_dir / "performance.json").is_file():
        print(f"Error: {run_dir} no contiene una función representada.", file=sys.stderr)
        return 2
    try:
        data = recompute(run_dir)
    except ASGError as exc:
        print(f"Error: {exc.public_message()}", file=sys.stderr)
        return 1
    destination = run_dir / OUTPUT_NAME
    atomic_write_json(destination, data)
    print(f"Métricas recalculadas en {destination}")
    return 0
