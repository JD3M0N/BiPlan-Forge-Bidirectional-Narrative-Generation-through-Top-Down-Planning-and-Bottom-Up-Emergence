"""Read what one stored performance produced, for the process features of a run.

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

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .artifacts import load_json_object, number_field, text_field
from .artifacts import read_json_lines as _lines

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
    "props",
    "item_actions",
    "item_repairs",
    "props_used_ratio",
    "hidden_item_actions",
    "secret_handoffs",
    "item_witness_share",
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
    inventory: str = "sin inventario"


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
        # A performance before 7.6 could not track objects, so a run that is silent ran without.
        inventory="con inventario"
        if (load_json_object(run_dir / "performance.json").get("settings") or {}).get("inventory")
        else "sin inventario",
    )


def _text(document: dict, field_name: str) -> str:
    """Read one string field, falling back to a stable placeholder."""
    return text_field(document, field_name) or UNKNOWN


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


def aggregate_calls(items: Iterable[dict], keys: tuple[str, ...]) -> list[dict]:
    """Sum logical calls, attempts, tokens and latency per combination of keys.

    A token count is no call, and a record without call_id cannot be regrouped, so neither
    counts. Rows come back sorted by their keys.
    """
    groups: dict[tuple[str, ...], dict] = {}
    for item in items:
        if item.get("operation") == "count_tokens" or not item.get("call_id"):
            continue
        key = tuple(str(item.get(name) or "") for name in keys)
        group = groups.setdefault(
            key,
            {
                **dict(zip(keys, key, strict=True)),
                "call_ids": set(),
                "tokens": 0,
                "latency_seconds": 0.0,
            },
        )
        group["call_ids"].add(item["call_id"])
        group["tokens"] += item.get("total_tokens") or 0
        group["latency_seconds"] += item.get("duration_seconds") or 0.0
    rows = []
    for _, group in sorted(groups.items()):
        call_ids = group.pop("call_ids")
        rows.append(
            {
                **group,
                "calls": len(call_ids),
                "latency_seconds": round(group["latency_seconds"], 3),
            }
        )
    return rows


def _agent_costs(run_dir: Path) -> list[dict]:
    """Aggregate logical calls, token use and attempt latency by agent and model."""
    columns = ("stage", "agent", "model", "calls", "tokens", "latency_seconds")
    return [
        {name: row[name] for name in columns}
        for row in aggregate_calls(_lines(run_dir / "llm_calls.jsonl"), columns[:3])
    ]
