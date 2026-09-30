"""Aggregate what every stored performance produced, for comparing simulated corpora.

Reads only JSON, like the rest of this package: it never imports the pipeline, so a run can be
studied long after the code that wrote it has moved on. The axes it groups by are the knobs the
thesis turns - the narrative voice, the actor memory model, the narrative profile and the
generator version - and the figures it reports are the ones a reader of the run could recompute
by hand from performance.json.

A figure a run never recorded is reported as not measured, never as zero. The 7.1 measurements
(gesture repetition, first-person actions, compression...) do not exist in a 7.0 run, and
reading them as 0 would make the older corpus look spotless on exactly the problems it had.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median

from .artifacts import group_by, load_json_object, number_field, text_field

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
    "beats_intervened",
    "turns_per_beat",
    "director_checks",
    "stage_events",
    "reaction_turns",
    "coda_turns",
    "rejected_turns",
    "skipped_turns",
    "speech_words",
    "action_words",
    "thought_words",
    "whispers",
    "repetition_ratio",
    "action_repetition_ratio",
    "first_person_actions",
    "thought_ratio",
    "long_speeches",
    "yields",
    "max_tactic_streak",
    "gates_known_by_discoverer",
    "mean_self_similarity",
    "script_echo",
    "unknown_mentions",
    "memory_records",
    "retrievals",
    "narration_source_fallbacks",
    "narrated_words",
    "compression_ratio",
    "dialogue_survival",
    "logged_turns",
    "logged_contexts",
    "context_coverage",
    "addressed_turns",
    "next_addressee_turns",
    "memory_ids_per_turn",
    "logged_attempts",
    "unresolved_attempts",
    "logged_proofs",
    "logged_facts",
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
    values: dict[str, float | None] = field(default_factory=dict)
    costs: list[dict] = field(default_factory=list)
    simulation_mode: str = "fixed"


@dataclass
class SimulationSummary:
    """Central tendency of one group of performances."""

    label: str
    runs: int
    values: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)


SIMULATION_GROUPINGS: dict[str, Callable[[SimulationRecord], str]] = {
    "story": lambda record: record.story,
    "voice": lambda record: record.narrative_voice,
    "memory": lambda record: record.actor_memory,
    "profile": lambda record: record.narrative_profile,
    "version": lambda record: record.generator_version,
    "voice-memory": lambda record: f"{record.narrative_voice} / {record.actor_memory}",
    "mode": lambda record: record.simulation_mode,
}


def discover_simulations(stories_root: str | Path) -> list[Path]:
    """Return every run directory that holds a performance, in a stable order."""
    root = Path(stories_root)
    if not root.is_dir():
        return []
    candidates = {path.parent for path in root.rglob(METRICS_FILENAME)}
    candidates.update(path.parents[2] for path in root.rglob("stage/*/turns.jsonl"))
    return sorted(
        item
        for item in candidates
        if load_json_object(item / "metadata.json").get("story_format") == "simulated"
    )


def read_simulation(directory: str | Path, stories_root: str | Path) -> SimulationRecord | None:
    """Describe one performed run, or None when its metrics cannot be read."""
    run_dir, root = Path(directory), Path(stories_root)
    metrics = load_json_object(run_dir / METRICS_FILENAME)
    metadata = load_json_object(run_dir / "metadata.json")
    if metadata.get("story_format") != "simulated" or not (
        metrics or list((run_dir / "stage").glob("*/turns.jsonl"))
    ):
        return None
    observed = _observed_logs(run_dir)
    version = load_json_object(run_dir / "generator_version.json")
    return SimulationRecord(
        directory=run_dir,
        run_id=run_dir.name,
        story=run_dir.relative_to(root).as_posix()
        if run_dir.is_relative_to(root)
        else run_dir.name,
        narrative_profile=_text(metrics, "narrative_profile")
        if metrics
        else _text(metadata, "narrative_profile"),
        narrative_voice=_text(metrics, "narrative_voice")
        if metrics
        else _text(metadata, "narrative_voice"),
        actor_memory=_text(metrics, "actor_memory") if metrics else _text(metadata, "actor_memory"),
        generator_version=_text(version, "generator_version"),
        status=_text(metadata, "status"),
        warnings=len(metadata.get("warnings") or []),
        values={
            name: observed.get(name, number_field(metrics, name)) for name in SIMULATION_FIELDS
        },
        costs=_agent_costs(run_dir),
        simulation_mode=load_json_object(run_dir / "generation_options.json").get(
            "simulation_mode", "fixed"
        ),
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
    """Group performances and report the mean and median of every field that was measured."""
    summaries = []
    for label, group in group_by(records, lambda record: key(record) or UNKNOWN).items():
        values = {}
        for name in SIMULATION_FIELDS:
            numbers = [value for record in group if (value := record.values[name]) is not None]
            values[name] = (
                (sum(numbers) / len(numbers), median(numbers)) if numbers else (None, None)
            )
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
        *("" if record.values[name] is None else record.values[name] for name in SIMULATION_FIELDS),
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


def _text(document: dict, field_name: str) -> str:
    """Read one string field, falling back to a stable placeholder."""
    return text_field(document, field_name) or UNKNOWN


def _lines(path: Path) -> list[dict]:
    """Read valid JSON objects from an append-only log, tolerating a torn last line."""
    if not path.is_file():
        return []
    try:
        raw = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    found = []
    for line in raw:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            found.append(value)
    return found


def _observed_logs(run_dir: Path) -> dict[str, float | None]:
    """Derive explicitly named log measures without inventing missing historical fields."""
    scenes = sorted((run_dir / "stage").glob("*/turns.jsonl"))
    if not scenes:
        return {}
    turns = [item for path in scenes for item in _lines(path)]
    actors = [item for item in turns if item.get("kind", "actor") == "actor"]
    contexts = [item for path in scenes for item in _lines(path.with_name("contexts.jsonl"))]
    attempts = [item for path in scenes for item in _lines(path.with_name("attempts.jsonl"))]
    directions = [item for path in scenes for item in _lines(path.with_name("director.jsonl"))]
    has_context_log = any(path.with_name("contexts.jsonl").exists() for path in scenes)
    context_ids = {item.get("turn_id") for item in contexts}
    addressed = [item for item in actors if item.get("addressed_to")]
    next_addressee = 0
    for left, right in zip(actors, actors[1:], strict=False):
        if right.get("actor_id") in (left.get("addressed_to") or []):
            next_addressee += 1
    requested = {item.get("id") for item in attempts if item.get("status") == "requested"}
    finished = {
        item.get("id")
        for item in attempts
        if item.get("status") in {"accepted", "rejected", "failed"}
    }
    return {
        "logged_turns": float(len(turns)),
        "logged_facts": float(len(_lines(run_dir / "stage/facts.jsonl")))
        if (run_dir / "stage/facts.jsonl").is_file()
        else None,
        "logged_contexts": float(len(contexts)) if has_context_log else None,
        "context_coverage": (
            len(context_ids & {item.get("id") for item in actors}) / len(actors)
            if actors and has_context_log
            else None
        ),
        "addressed_turns": float(len(addressed)),
        "next_addressee_turns": float(next_addressee),
        "memory_ids_per_turn": sum(len(item.get("retrieved_memory_ids") or []) for item in actors)
        / len(actors)
        if actors
        else None,
        "logged_attempts": float(len(requested))
        if any(path.with_name("attempts.jsonl").exists() for path in scenes)
        else None,
        "unresolved_attempts": float(len(requested - finished)) if requested else None,
        "logged_proofs": float(sum(len(item.get("proofs") or []) for item in directions))
        if any("proofs" in item for item in directions)
        else None,
    }


def _agent_costs(run_dir: Path) -> list[dict]:
    """Aggregate logical calls, token use and attempt latency by agent and model."""
    groups: dict[tuple[str, str, str], dict] = {}
    for item in _lines(run_dir / "llm_calls.jsonl"):
        if item.get("operation") == "count_tokens" or not item.get("call_id"):
            continue
        key = (
            str(item.get("stage") or ""),
            str(item.get("agent") or ""),
            str(item.get("model") or ""),
        )
        group = groups.setdefault(
            key,
            {
                "stage": key[0],
                "agent": key[1],
                "model": key[2],
                "call_ids": set(),
                "tokens": 0,
                "latency_seconds": 0.0,
            },
        )
        group["call_ids"].add(item["call_id"])
        group["tokens"] += item.get("total_tokens") or 0
        group["latency_seconds"] += item.get("duration_seconds") or 0.0
    return [
        {
            "stage": value["stage"],
            "agent": value["agent"],
            "model": value["model"],
            "calls": len(value["call_ids"]),
            "tokens": value["tokens"],
            "latency_seconds": round(value["latency_seconds"], 3),
        }
        for _, value in sorted(groups.items())
    ]
