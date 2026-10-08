"""Unified feature tables and explicitly observational configuration comparisons."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .artifacts import load_json_object
from .catalog import catalog, catalog_snapshot, digest
from .features import deterministic_features, entropy, measurement
from .pairing import read_run_config
from .simulation_report import _agent_costs, read_simulation
from .study import StudyRepository

DIRECT = {
    "P09": ("promise_audit", "fulfilled_ratio"),
    "P10": ("promise_audit", "broken"),
    "P14": ("script_metrics", "scenes"),
    "P15": ("script_metrics", "dialogue_word_ratio"),
    "P16": ("script_metrics", "idle_cast"),
    "P17": ("script_metrics", "absent_participants"),
    "P19": ("simulation_metrics", "beat_completion_ratio"),
    "P20": ("simulation_metrics", "beats_forced"),
    "P21": ("simulation_metrics", "stage_events"),
    "P22": ("simulation_metrics", "whispers"),
    "P23": ("simulation_metrics", "yields"),
    "P25": ("simulation_metrics", "max_tactic_streak"),
    "P26": ("simulation_metrics", "script_echo"),
    "P27": ("simulation_metrics", "unknown_mentions"),
    "P28": ("simulation_metrics", "repetition_ratio"),
    "P29": ("simulation_metrics", "action_repetition_ratio"),
    "P30": ("simulation_metrics", "thought_ratio"),
    "P33": ("simulation_metrics", "compression_ratio"),
    "P34": ("simulation_metrics", "dialogue_survival"),
    "P39": ("simulation_metrics", "item_actions"),
    "P40": ("simulation_metrics", "props_used_ratio"),
    "P41": ("simulation_metrics", "secret_handoffs"),
    "P42": ("simulation_metrics", "item_witness_share"),
    "P44": ("metadata", "status"),
    "K01": ("llm_usage", "calls"),
    "K02": ("llm_usage", "total_tokens"),
    "K03": ("llm_usage", "failed_attempts"),
    "K05": ("llm_usage", "total_wait_seconds"),
    "C18": ("source_run", "run_id"),
}
CONFIG = dict(
    zip(
        (f"C{i:02}" for i in range(2, 18)),
        (
            "story_format",
            "script_method",
            "narrative_profile",
            "promise_ledger",
            "narrative_guidance",
            "narrative_voice",
            "narrator",
            "narration_tone",
            "actor_memory",
            "simulation_mode",
            "inventory",
            "turns_per_beat",
            "model",
            "stage_model",
            "pipeline_version",
            "work",
        ),
        strict=True,
    )
)


def _list(document: dict, key: str) -> list | None:
    """Accept only actual recorded lists, leaving missing values undefined."""
    value = document.get(key)
    return value if isinstance(value, list) else None


def _ratio(numerator: float, denominator: float) -> float | None:
    """Leave empty-denominator ratios undefined."""
    return numerator / denominator if denominator else None


def _counts(documents: dict, directory: Path) -> dict:
    """Derive plan, review and prose-process counts from recorded fields only."""
    values = {}
    specifications = {
        "P01": ("story_plan", "events"),
        "P05": ("plan_review", "notes"),
        "P06": ("characters", "characters"),
        "P08": ("promise_audit", "promises"),
        "P43": ("metadata", "warnings"),
    }
    for key, (source, field) in specifications.items():
        rows = _list(documents[source], field)
        if rows is not None:
            values[key] = len(rows)
    events = _list(documents["story_plan"], "events")
    dependencies = _list(documents["story_plan"], "dependencies")
    if events is not None:
        values["P03"] = sum(bool(e.get("payoff_of")) for e in events if isinstance(e, dict))
        if dependencies is not None:
            values["P02"] = _ratio(len(dependencies), len(events))
    if (directory / "planning").is_dir():
        values["P04"] = len(list((directory / "planning").glob("attempt-*-validation.json")))
    world = documents["world"]
    if _list(world, "locations") is not None and _list(world, "objects") is not None:
        values["P07"] = len(world["locations"]) + len(world["objects"])
    notes = _list(documents["review"], "notes")
    if notes is not None:
        values["P11"] = sum(
            n.get("priority") in {"critical", "major"} for n in notes if isinstance(n, dict)
        )
    checks = _list(documents["review"], "constraint_checks")
    if checks is not None:
        values["P12"] = _ratio(
            sum(c.get("passed") is True for c in checks if isinstance(c, dict)), len(checks)
        )
    revision = _list(documents["revision_report"], "chapters")
    if revision and all(
        isinstance(c.get("draft_words"), int) and isinstance(c.get("final_words"), int)
        for c in revision
    ):
        values["P13"] = _ratio(
            sum(c["final_words"] for c in revision), sum(c["draft_words"] for c in revision)
        )
    return values


def _simulation_counts(documents: dict, directory: Path) -> dict:
    """Aggregate per-actor and observation logs without substituting text counts."""
    values = {}
    for key, source, field in (
        ("P18", "script_metrics", "lines"),
        ("P24", "simulation_metrics", "distinct_tactics"),
    ):
        actors = documents[source].get("character_metrics" if key == "P18" else "actor_metrics")
        if isinstance(actors, dict):
            actors = list(actors.values())
        if (
            isinstance(actors, list)
            and actors
            and all(isinstance(a.get(field), int) for a in actors)
        ):
            counts = [a[field] for a in actors]
            values[key] = entropy(counts) if key == "P18" else statistics.mean(counts)
    gates = _list(documents["cast_bible"], "knowledge_gates")
    if gates is not None:
        values["P36"] = dict(Counter(g.get("how", "unknown") for g in gates if isinstance(g, dict)))
    chapters = _list(documents["narration"], "chapters")
    if chapters is not None:
        values["P38"] = sum(c.get("source") == "absent" for c in chapters if isinstance(c, dict))
    simulation = read_simulation(directory, directory.parent)
    if simulation:
        values["P31"] = simulation.values.get("memory_ids_per_turn")
        turns = simulation.values.get("turns")
        addressed = simulation.values.get("addressed_turns")
        if turns is not None and addressed is not None:
            values["P32"] = _ratio(addressed, turns)
        values["K06"] = simulation.costs or None
    scenes = _list(documents["performance"], "scenes")
    if scenes is not None:
        counts = Counter(
            t["actor_id"]
            for s in scenes
            if isinstance(s, dict)
            for t in s.get("turns", [])
            if t.get("actor_id")
        )
        values["P35"] = {
            "turns": dict(counts),
            "maximum_share": _ratio(max(counts.values(), default=0), sum(counts.values())),
            "entropy": entropy(list(counts.values())),
        }
    return values


def process_features(directory: Path) -> dict:
    """Read every currently observable process, cost and configuration feature."""
    names = {source for source, _ in DIRECT.values()} | {
        "story_plan",
        "plan_review",
        "characters",
        "world",
        "review",
        "revision_report",
        "cast_bible",
        "narration",
        "performance",
        "generation_options",
    }
    documents = {name: load_json_object(directory / f"{name}.json") for name in names}
    values = {key: documents[source].get(field) for key, (source, field) in DIRECT.items()}
    values.update(_counts(documents, directory))
    values.update(_simulation_counts(documents, directory))
    values["K06"] = _agent_costs(directory) or None
    config = read_run_config(directory)
    values.update({key: config.axes.get(field) for key, field in CONFIG.items()})
    values["C16"] = config.pipeline_version
    fmt = values["C02"]
    values["C01"] = (
        "Baseline"
        if fmt == "baseline"
        else "Hybrid"
        if fmt == "simulated"
        else "Top-Down"
        if directory.parent.name in {"Stagecraft", "Top-Down"}
        else directory.parent.name
    )
    metadata = documents["metadata"]
    try:
        values["K04"] = (
            datetime.fromisoformat(metadata["updated_at"])
            - datetime.fromisoformat(metadata["created_at"])
        ).total_seconds()
    except (KeyError, TypeError, ValueError):
        pass
    return {
        key: measurement(value, status="measured" if value is not None else "missing")
        for key, value in values.items()
    }


def study_extractions(db: str | Path) -> dict[str, dict]:
    """Index a frozen study's feature sidecars by text hash, read-only and without calls."""
    db = Path(db)
    if not db.is_file():
        raise ValueError("No existe la base del estudio.")
    return {
        story["text_hash"]: report
        for story in StudyRepository(db).export()["stories"]
        if (report := load_json_object(db.parent / "features" / f"{story['id']}.json"))
    }


def _compatible(report: dict, text_hash: str) -> bool:
    """Accept an extraction only for this exact text and the current catalog."""
    identity = report.get("identity", {})
    return (
        identity.get("text_hash") == text_hash
        and identity.get("catalog_hash") == catalog_snapshot()["sha256"]
    )


def read_features(directory: str | Path, *, extractions: dict[str, dict] | None = None) -> dict:
    """Merge recomputed text counts, compatible extractions and tolerant process readers."""
    directory = Path(directory)
    text = (directory / "story.md").read_text(encoding="utf-8")
    text_hash = digest(text)
    result = {key: measurement(status="missing") for key in catalog()}
    extracted = load_json_object(directory / "features" / "features.json")
    if not _compatible(extracted, text_hash):
        extracted = (extractions or {}).get(text_hash, {})
    compatible = _compatible(extracted, text_hash)
    if compatible:
        result.update(extracted.get("features", {}))
    result.update(deterministic_features(text))
    result.update(process_features(directory))
    definitions = catalog()
    for key, value in result.items():
        value["unit"] = definitions[key]["unidad"]
    config = read_run_config(directory)
    return {
        "story": str(directory),
        "run_id": directory.name,
        "text_hash": text_hash,
        "status": config.status,
        "generator_version": config.generator_version,
        "pipeline_version": config.pipeline_version,
        "format": config.axes.get("story_format"),
        "extraction_compatible": compatible,
        "extraction_identity": extracted.get("identity", {}) if compatible else {},
        "features": result,
    }


def horizontal_report(rows: list[dict], axis: str = "C02") -> dict:
    """Summarize observed differences while separating generator and pipeline versions."""
    if axis not in catalog() or not axis.startswith("C"):
        raise ValueError("El eje horizontal debe ser un campo C del catálogo.")
    groups = defaultdict(list)
    for row in rows:
        key = (
            row.get("generator_version"),
            row.get("pipeline_version"),
            json.dumps(row["features"][axis]["value"], ensure_ascii=False, sort_keys=True),
        )
        groups[key].append(row)
    summaries = []
    for (generator, pipeline, value), group in groups.items():
        stats = {}
        for key in catalog():
            numbers = [
                r["features"][key]["value"]
                for r in group
                if r["features"][key]["status"] == "measured"
                and isinstance(r["features"][key]["value"], int | float)
            ]
            if numbers:
                stats[key] = {
                    "n": len(numbers),
                    "median": statistics.median(numbers),
                    "min": min(numbers),
                    "max": max(numbers),
                }
        summaries.append(
            {
                "generator_version": generator,
                "pipeline_version": pipeline,
                "axis_value": json.loads(value),
                "stories": len(group),
                "features": stats,
            }
        )
    return {
        "axis": axis,
        "groups": summaries,
        "interpretation": (
            "Asociaciones observacionales; prompts y opciones libres no aíslan efectos causales."
        ),
    }
