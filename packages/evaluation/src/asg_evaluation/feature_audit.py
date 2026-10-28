"""Extraction stability, log comparison and human evidence-review worksheets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from asg_core import atomic_write_json, use_utf8_output

from .artifacts import load_json_object
from .catalog import digest
from .features import entropy
from .simulation_report import lie_turns, logged_actor_turns

# The text may stay under the log (the narrator cuts) but not rise above it by more than this.
CEILING_RELATIVE = 1.10
CEILING_ABSOLUTE = 1
NO_LOG = "El run no guardó el log de turnos (stage/*/turns.jsonl)."
NO_INVENTORY = "El run no llevó inventario (anterior a 7.6 o apagado)."
NO_CEILING = "El log no es un techo para este rasgo: es una distribución, no un recuento."

# text feature, log figure, whether the log is a ceiling, and what the log figure is
LOG_PAIRS = (
    ("X02", "P35", "presence_share", False, "escenas con turno del actor más presente / escenas"),
    ("X03", "P35", "presence_entropy", False, "entropía de las escenas con turno por actor"),
    ("X08", "turns.jsonl", "speech_turns", True, "turnos de actor con réplica"),
    ("X29", "turns.jsonl", "speech_entropy", False, "entropía de las réplicas por actor"),
    ("X10", "P37", "lies", True, "turnos con táctica lie"),
    ("X13", "P36", "gates", True, "compuertas de conocimiento planificadas"),
    ("X16", "P21", "world_events", True, "intervenciones del director (stage_event)"),
    ("X17", "P39", "item_actions", True, "movimientos de objeto arbitrados"),
    ("X18", "P40", "props_used", True, "objetos colocados que se llegaron a manejar"),
)


def compare_extractions(first: dict, second: dict) -> dict:
    """Compare repeated measurements of the same text without imposing a log ceiling."""
    if first["identity"]["text_hash"] != second["identity"]["text_hash"]:
        raise ValueError("El test-retest requiere exactamente el mismo texto.")
    comparisons = {}
    for key in sorted(set(first["features"]) | set(second["features"])):
        left, right = first["features"].get(key, {}), second["features"].get(key, {})
        a, b = left.get("value"), right.get("value")
        valid = left.get("status") == right.get("status") == "measured"
        comparisons[key] = {
            "first_status": left.get("status"),
            "second_status": right.get("status"),
            "equal": a == b if valid else None,
            "delta": b - a
            if valid and isinstance(a, int | float) and isinstance(b, int | float)
            else None,
        }
    return {"same_protocol": first["identity"] == second["identity"], "features": comparisons}


def _missing(reason: str) -> dict:
    """Describe a log figure the run never recorded; it is never read as zero."""
    return {"value": None, "reason": reason}


def _figure(value: float | None, reason: str) -> dict:
    """Wrap one log figure, or its absence, with the reason it is absent."""
    return {"value": value, "reason": ""} if value is not None else _missing(reason)


def _log_figures(run_dir: Path, turns: list[dict]) -> dict:
    """Read every log figure the text counts are compared against, for one run."""
    scenes = {t.get("scene_id") for t in turns}
    present = Counter(
        actor for actor, _ in {(t.get("actor_id"), t.get("scene_id")) for t in turns} if actor
    )
    spoken = Counter(t.get("actor_id") for t in turns if t.get("speech"))
    metrics = load_json_object(run_dir / "simulation_metrics.json")
    gates = load_json_object(run_dir / "cast_bible.json").get("knowledge_gates")
    props, ratio = metrics.get("props"), metrics.get("props_used_ratio")
    return {
        "presence_share": _figure(max(present.values()) / len(scenes) if present else None, NO_LOG),
        "presence_entropy": _figure(entropy(list(present.values())) if present else None, NO_LOG),
        "speech_turns": _figure(sum(spoken.values()) if turns else None, NO_LOG),
        "speech_entropy": _figure(entropy(list(spoken.values())) if turns else None, NO_LOG),
        "lies": _figure(
            lie_turns(run_dir),
            "Ningún turno del log registra la táctica (run anterior a la táctica).",
        ),
        "gates": _figure(
            len(gates) if isinstance(gates, list) else None,
            "cast_bible.json no registra compuertas de conocimiento.",
        ),
        "world_events": _figure(
            metrics.get("stage_events"), "simulation_metrics.json no registra eventos del mundo."
        ),
        "item_actions": _figure(metrics.get("item_actions"), NO_INVENTORY),
        "props_used": _figure(
            round(props * ratio)
            if isinstance(props, int | float) and isinstance(ratio, int | float)
            else None,
            NO_INVENTORY,
        ),
    }


def _violates(text: float, log: float) -> bool:
    """Say whether the text rises above the log by more than the tolerated margin."""
    return text > max(log * CEILING_RELATIVE, log + CEILING_ABSOLUTE)


def _same_name(left: str, right: str) -> bool:
    """Match a text label with a cast name, ignoring case and extra words."""
    a, b = set(left.casefold().split()), set(right.casefold().split())
    return bool(a and b) and (a <= b or b <= a)


def _speech_by_actor(run_dir: Path, turns: list[dict], text_feature: dict) -> list[dict]:
    """Pair each cast member's logged replicas with the text's count for that speaker."""
    cast = load_json_object(run_dir / "characters.json").get("characters")
    names = {c.get("id"): c.get("name") or "" for c in cast if isinstance(c, dict)} if cast else {}
    labels = {k: v.get("raw") for k, v in (text_feature.get("breakdown") or {}).items()}
    rows = []
    for actor, logged in sorted(Counter(t["actor_id"] for t in turns if t.get("speech")).items()):
        label = next((k for k in labels if _same_name(k, names.get(actor) or actor)), None)
        text = labels.pop(label) if label else None
        rows.append(
            {
                "actor": actor,
                "text_label": label,
                "text": text,
                "log": logged,
                "violates_ceiling": _violates(text, logged) if text is not None else None,
            }
        )
    return rows


def compare_with_logs(extraction: dict, run_dir: str | Path) -> dict:
    """Compare each extracted count with the run's own log, reading files only.

    Every pair reports the text value, the log value and, when the log is a ceiling, whether
    the text rises above it. A figure the run did not record is "not_measured" with the
    reason, never zero.
    """
    run_dir = Path(run_dir)
    story = run_dir / "story.md"
    if story.is_file() and digest(story.read_text(encoding="utf-8")) != extraction.get(
        "identity", {}
    ).get("text_hash"):
        raise ValueError("La extracción no corresponde al story.md de este run.")
    turns = logged_actor_turns(run_dir)
    figures = _log_figures(run_dir, turns)
    pairs = []
    for feature, log_feature, figure, ceiling, meaning in LOG_PAIRS:
        text = extraction.get("features", {}).get(feature, {})
        log = figures[figure]
        row = {
            "feature": feature,
            "log_feature": log_feature,
            "log_meaning": meaning,
            "ceiling": ceiling,
            "text_status": text.get("status", "missing"),
            "text_value": text.get("raw" if ceiling else "value"),
            "log_value": log["value"],
            "status": "compared",
            "reason": "" if ceiling else NO_CEILING,
            "violates_ceiling": None,
        }
        if row["text_status"] != "measured":
            row.update(
                status="not_measured",
                reason=text.get("reason") or "El texto no tiene este rasgo medido.",
            )
        elif log["value"] is None:
            row.update(status="not_measured", reason=log["reason"])
        elif ceiling:
            row["violates_ceiling"] = _violates(row["text_value"], log["value"])
        if feature == "X08" and row["status"] == "compared":
            row["by_actor"] = _speech_by_actor(run_dir, turns, text)
        pairs.append(row)
    return {"run": run_dir.name, "logged": bool(turns), "pairs": pairs}


def review_worksheet(report: dict) -> list[dict]:
    """Expose all observations and zero claims for semantic review, including missed events."""
    result = []
    for key, feature in report["features"].items():
        if key.startswith(("R", "X")):
            result.append(
                {
                    "feature": key,
                    "status": feature["status"],
                    "value": feature["value"],
                    "evidence": feature["evidence"],
                    "human_verdict": None,
                    "missed_occurrences": [],
                    "notes": "",
                }
            )
    return result


def main(argv: list[str] | None = None) -> int:
    """Write review worksheets, test-retest differences and log comparisons without calls."""
    parser = argparse.ArgumentParser(description="Auditar estabilidad y evidencias del extractor")
    parser.add_argument("first", type=Path)
    parser.add_argument("--second", type=Path)
    parser.add_argument("--run", type=Path, help="Run simulado cuyo log se contrasta")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    use_utf8_output()
    first = load_json_object(args.first)
    report = {"identity": first["identity"], "review": review_worksheet(first)}
    if args.second:
        report["test_retest"] = compare_extractions(first, load_json_object(args.second))
    if args.run:
        report["log_comparison"] = compare_with_logs(first, args.run)
    atomic_write_json(args.output, report)
    print(json.dumps({"output": str(args.output)}, ensure_ascii=False))
    return 0
