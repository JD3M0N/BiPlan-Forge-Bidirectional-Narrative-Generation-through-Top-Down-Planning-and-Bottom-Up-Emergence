"""Extraction stability, log comparison and human evidence-review worksheets."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from asg_core import atomic_write_json, use_utf8_output

from .artifacts import load_json_object
from .catalog import catalog, core_ids, digest
from .features import DERIVED, entropy, paragraphs
from .simulation_report import lie_turns, logged_actor_turns

# The text may stay under the log (the narrator cuts) but not rise above it by more than this.
CEILING_RELATIVE = 1.10
CEILING_ABSOLUTE = 1
NO_LOG = "El run no guardó el log de turnos (stage/*/turns.jsonl)."
NO_INVENTORY = "El run no llevó inventario (anterior a 7.6 o apagado)."
# Thresholds fixed in decisions.md section 2 (P04.3) before any measurement.
MIN_JUDGED = 5
RETEST_MAX_DIFFERENCE = 0.25
RETEST_MAX_STATE_CHANGES = 1
SHEET_COLUMNS = (
    "rasgo",
    "nombre",
    "estado",
    "valor",
    "ocurrencia",
    "cita",
    "parrafo",
    "veredicto",
    "ocurrencias_omitidas",
    "notas",
)
VERDICTS = {"correcto": "correct", "incorrecto": "incorrect", "dudoso": "doubtful"}
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


def _sheet_keys(extraction: dict, scope: str) -> list[str]:
    """Pick the features a person reviews: all, or the P04.3 sample for the partial scope."""
    rows = catalog()
    unlogged = {k for k in core_ids() if not rows[k]["validable_contra"]} | {"X05", "X23"}
    keys = []
    for key, row in rows.items():
        feature = extraction["features"].get(key)
        if feature is None or row["capa"] not in {"R", "X"} or key in DERIVED:
            continue
        hollow = feature["status"] != "measured" or feature["value"] == 0
        if scope == "completa" or key in unlogged or hollow:
            keys.append(key)
    return keys


def _quotes(occurrence: dict, blocks: list[dict]) -> tuple[str, str]:
    """Render an occurrence's quotes and the paragraphs that contain them."""
    quotes, containing = [], []
    for quote in occurrence["evidence"]:
        number = quote["paragraph"]
        if number >= len(blocks) or quote["text"] not in blocks[number]["text"]:
            raise ValueError(f"La cita del párrafo {number} no está en el texto.")
        quotes.append(f"[¶{number}] {quote['text']}")
        containing.append(f"[¶{number}] {blocks[number]['text']}")
    return "\n".join(quotes), "\n\n".join(containing)


def review_sheet(extraction: dict, text: str, scope: str = "completa") -> list[dict]:
    """Build one row per extracted occurrence, plus one per feature with none (zero, n/a, failed).

    Rows without occurrences are where omissions hide, so the reviewer notes them there.
    """
    if scope not in {"completa", "parcial"}:
        raise ValueError("El alcance es «completa» o «parcial».")
    if digest(text) != extraction["identity"]["text_hash"]:
        raise ValueError("La extracción no corresponde a este texto.")
    blocks = paragraphs(text)
    names = catalog()
    rows = []
    for key in _sheet_keys(extraction, scope):
        feature = extraction["features"][key]
        base = {
            "rasgo": key,
            "nombre": names[key]["nombre"],
            "estado": feature["status"],
            "valor": "" if feature["value"] is None else feature["value"],
            "veredicto": "",
            "ocurrencias_omitidas": "",
            "notas": "",
        }
        for number, occurrence in enumerate(feature["evidence"], 1):
            cited, context = _quotes(occurrence, blocks)
            label = ": ".join(x for x in (occurrence.get("label"), occurrence["explanation"]) if x)
            rows.append(
                {**base, "ocurrencia": f"{number}. {label}", "cita": cited, "parrafo": context}
            )
        if not feature["evidence"]:
            rows.append(
                {**base, "ocurrencia": "", "cita": "", "parrafo": "", "notas": feature["reason"]}
            )
    return rows


def write_sheet(rows: list[dict], path: str | Path) -> None:
    """Write the review sheet as CSV that Excel opens with accents intact."""
    with open(path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def verdict_summary(sheets: list[str | Path]) -> dict:
    """Aggregate filled sheets into per-feature precision and coverage (thresholds in P04.3)."""
    counts: dict[str, Counter] = {}
    for path in sheets:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                tally = counts.setdefault(row["rasgo"], Counter())
                omitted = (row.get("ocurrencias_omitidas") or "").strip()
                if omitted:
                    if not omitted.isdigit():
                        raise ValueError(f"{row['rasgo']}: omitidas debe ser un entero: {omitted}")
                    tally["omitted"] += int(omitted)
                verdict = (row.get("veredicto") or "").strip().casefold()
                if not verdict or not row["ocurrencia"]:
                    continue
                if verdict not in VERDICTS:
                    raise ValueError(f"{row['rasgo']}: veredicto desconocido «{verdict}».")
                tally[VERDICTS[verdict]] += 1
    result = {}
    for key, tally in sorted(counts.items()):
        judged = tally["correct"] + tally["incorrect"]
        found = tally["correct"] + tally["omitted"]
        result[key] = {
            "correct": tally["correct"],
            "incorrect": tally["incorrect"],
            "doubtful": tally["doubtful"],
            "omitted": tally["omitted"],
            "judged": judged,
            "precision": tally["correct"] / judged if judged else None,
            "coverage": tally["correct"] / found if found else None,
            "insufficient_evidence": judged < MIN_JUDGED,
        }
    return result


def _ranks(values: list[float]) -> list[float]:
    """Rank values from 1, giving tied values the average of their positions."""
    ordered = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start
        while end + 1 < len(ordered) and values[ordered[end + 1]] == values[ordered[start]]:
            end += 1
        for index in ordered[start : end + 1]:
            ranks[index] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def spearman(left: list[float], right: list[float]) -> float | None:
    """Rank correlation of two series; None when fewer than 3 points or a series is constant."""
    if len(left) < 3:
        return None
    a, b = _ranks(left), _ranks(right)
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    spread = (sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b)) ** 0.5
    return cov / spread if spread else None


def retest_summary(pairs: list[tuple[dict, dict]]) -> dict:
    """Summarize repeated extractions per feature over several stories (agreement and drift)."""
    series: dict[str, dict] = {}
    for first, second in pairs:
        comparison = compare_extractions(first, second)["features"]
        for key, row in comparison.items():
            entry = series.setdefault(key, {"a": [], "b": [], "state_changes": 0, "stories": 0})
            entry["stories"] += 1
            entry["state_changes"] += row["first_status"] != row["second_status"]
            a = first["features"].get(key, {}).get("value")
            b = second["features"].get(key, {}).get("value")
            numeric = isinstance(a, int | float) and isinstance(b, int | float)
            if row["equal"] is not None and numeric:
                entry["a"].append(a)
                entry["b"].append(b)
    core = set(core_ids())
    result = {}
    for key, entry in sorted(series.items()):
        a, b = entry["a"], entry["b"]
        diffs = [abs(x - y) / max(abs(x), abs(y), 1) for x, y in zip(a, b, strict=True)]
        mean_difference = sum(diffs) / len(diffs) if diffs else None
        result[key] = {
            "core": key in core,
            "stories": entry["stories"],
            "measured_in_both": len(a),
            "exact_agreement": sum(x == y for x, y in zip(a, b, strict=True)) / len(a)
            if a
            else None,
            "mean_relative_difference": mean_difference,
            "rank_correlation": spearman(a, b),
            "state_changes": entry["state_changes"],
            "meets_threshold": mean_difference is not None
            and mean_difference <= RETEST_MAX_DIFFERENCE
            and entry["state_changes"] <= RETEST_MAX_STATE_CHANGES,
        }
    return result


def main(argv: list[str] | None = None) -> int:
    """Write review sheets, test-retest summaries and verdict totals without calls."""
    parser = argparse.ArgumentParser(description="Auditar estabilidad y evidencias del extractor")
    parser.add_argument("first", type=Path, nargs="?")
    parser.add_argument("--second", type=Path)
    parser.add_argument("--run", type=Path, help="Run simulado cuyo log se contrasta")
    parser.add_argument("--hoja", type=Path, help="CSV de revisión humana que se escribe")
    parser.add_argument("--texto", type=Path, help="story.md de la extracción, para --hoja")
    parser.add_argument("--alcance", choices=("completa", "parcial"), default="completa")
    parser.add_argument(
        "--pares", type=Path, nargs="+", help="Pares PRIMERA SEGUNDA de varias historias"
    )
    parser.add_argument("--veredictos", type=Path, nargs="+", help="Hojas rellenadas")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    use_utf8_output()
    report: dict = {}
    if args.first:
        first = load_json_object(args.first)
        report = {"identity": first["identity"], "review": review_worksheet(first)}
        if args.second:
            report["test_retest"] = compare_extractions(first, load_json_object(args.second))
        if args.run:
            report["log_comparison"] = compare_with_logs(first, args.run)
        if args.hoja:
            if not args.texto:
                parser.error("--hoja requiere --texto")
            text = args.texto.read_text(encoding="utf-8")
            write_sheet(review_sheet(first, text, args.alcance), args.hoja)
    if args.pares:
        if len(args.pares) % 2:
            parser.error("--pares requiere un número par de archivos")
        loaded = [load_json_object(path) for path in args.pares]
        pairs = list(zip(loaded[::2], loaded[1::2], strict=True))
        report["retest_summary"] = retest_summary(pairs)
    if args.veredictos:
        report["verdicts"] = verdict_summary(args.veredictos)
    if not report:
        parser.error("indica una extracción, --pares o --veredictos")
    atomic_write_json(args.output, report)
    print(json.dumps({"output": str(args.output)}, ensure_ascii=False))
    return 0
