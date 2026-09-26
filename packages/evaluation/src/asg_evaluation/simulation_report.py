"""Aggregate what every stored performance produced, for comparing simulated corpora.

Reads only JSON, like the rest of this package: it never imports the pipeline, so a run can be
studied long after the code that wrote it has moved on. The axes it groups by are the knobs the
thesis turns - the narrative voice, the actor memory model, the narrative profile and the
generator version - and the figures it reports are the ones a reader of the run could recompute
by hand from performance.json.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

METRICS_FILENAME = "simulation_metrics.json"
UNKNOWN = "desconocido"

# Every figure aggregated below, in report order. Ratios read as ratios and counts as counts,
# so the summary never mixes the two in one column.
SIMULATION_FIELDS: tuple[str, ...] = (
    "scenes",
    "turns",
    "beats",
    "beat_completion_ratio",
    "beats_forced",
    "turns_per_beat",
    "director_checks",
    "stage_events",
    "rejected_turns",
    "skipped_turns",
    "speech_words",
    "action_words",
    "thought_words",
    "whispers",
    "repetition_ratio",
    "mean_self_similarity",
    "script_echo",
    "unknown_mentions",
    "memory_records",
    "retrievals",
    "narration_source_fallbacks",
    "narrated_words",
    "dialogue_survival",
)


@dataclass
class SimulationRecord:
    """One performed run, described by the axes it was generated under."""

    directory: Path
    run_id: str
    story: str
    narrative_profile: str
    narrative_voice: str
    actor_memory: str
    generator_version: str
    status: str
    warnings: int
    values: dict[str, float] = field(default_factory=dict)


@dataclass
class SimulationSummary:
    """Central tendency of one group of performances."""

    label: str
    runs: int
    values: dict[str, tuple[float, float]] = field(default_factory=dict)


SIMULATION_GROUPINGS: dict[str, Callable[[SimulationRecord], str]] = {
    "story": lambda record: record.story,
    "voice": lambda record: record.narrative_voice,
    "memory": lambda record: record.actor_memory,
    "profile": lambda record: record.narrative_profile,
    "version": lambda record: record.generator_version,
    "voice-memory": lambda record: f"{record.narrative_voice} / {record.actor_memory}",
}


def discover_simulations(stories_root: str | Path) -> list[Path]:
    """Return every run directory that holds a performance, in a stable order."""
    root = Path(stories_root)
    if not root.is_dir():
        return []
    return sorted(path.parent for path in root.rglob(METRICS_FILENAME) if path.is_file())


def read_simulation(directory: str | Path, stories_root: str | Path) -> SimulationRecord | None:
    """Describe one performed run, or None when its metrics cannot be read."""
    run_dir, root = Path(directory), Path(stories_root)
    metrics = _load(run_dir / METRICS_FILENAME)
    if not metrics:
        return None
    metadata = _load(run_dir / "metadata.json")
    version = _load(run_dir / "generator_version.json")
    return SimulationRecord(
        directory=run_dir,
        run_id=run_dir.name,
        story=run_dir.relative_to(root).as_posix()
        if run_dir.is_relative_to(root)
        else run_dir.name,
        narrative_profile=_text(metrics, "narrative_profile"),
        narrative_voice=_text(metrics, "narrative_voice"),
        actor_memory=_text(metrics, "actor_memory"),
        generator_version=_text(version, "generator_version"),
        status=_text(metadata, "status"),
        warnings=len(metadata.get("warnings") or []),
        values={name: _number(metrics, name) for name in SIMULATION_FIELDS},
    )


def collect_simulations(stories_root: str | Path) -> list[SimulationRecord]:
    """Measure every performed run below a root, in discovery order."""
    root = Path(stories_root)
    found = (read_simulation(directory, root) for directory in discover_simulations(root))
    return [record for record in found if record is not None]


def summarize_simulations(
    records: Iterable[SimulationRecord],
    key: Callable[[SimulationRecord], str],
) -> list[SimulationSummary]:
    """Group performances and report the mean and median of every field."""
    grouped: dict[str, list[SimulationRecord]] = {}
    for record in records:
        grouped.setdefault(key(record) or UNKNOWN, []).append(record)
    summaries = []
    for label in sorted(grouped):
        group = grouped[label]
        values = {}
        for name in SIMULATION_FIELDS:
            numbers = [record.values[name] for record in group]
            values[name] = (sum(numbers) / len(numbers), median(numbers)) if numbers else (0.0, 0.0)
        summaries.append(SimulationSummary(label=label, runs=len(group), values=values))
    return summaries


def simulation_row(record: SimulationRecord) -> list[object]:
    """Flatten one performed run into its declared CSV columns."""
    return [
        record.story,
        record.run_id,
        record.narrative_profile,
        record.narrative_voice,
        record.actor_memory,
        record.generator_version,
        record.status,
        record.warnings,
        *(record.values[name] for name in SIMULATION_FIELDS),
    ]


SIMULATION_COLUMNS: tuple[str, ...] = (
    "story",
    "run_id",
    "narrative_profile",
    "narrative_voice",
    "actor_memory",
    "generator_version",
    "status",
    "warnings",
    *SIMULATION_FIELDS,
)


def _load(path: Path) -> dict:
    """Read one JSON artifact, treating a missing or broken file as absent."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return document if isinstance(document, dict) else {}


def _text(document: dict, field_name: str) -> str:
    """Read one string field, falling back to a stable placeholder."""
    value = document.get(field_name)
    return value if isinstance(value, str) and value.strip() else UNKNOWN


def _number(document: dict, field_name: str) -> float:
    """Read one numeric field, treating anything unreadable as zero."""
    value = document.get(field_name)
    return float(value) if isinstance(value, (int, float)) else 0.0
