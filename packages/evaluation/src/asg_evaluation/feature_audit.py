"""Extraction stability and human evidence-review worksheets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from asg_core import atomic_write_json, use_utf8_output

from .artifacts import load_json_object


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
    """Write review worksheets and optional test-retest differences without model calls."""
    parser = argparse.ArgumentParser(description="Auditar estabilidad y evidencias del extractor")
    parser.add_argument("first", type=Path)
    parser.add_argument("--second", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    use_utf8_output()
    first = load_json_object(args.first)
    report = {"identity": first["identity"], "review": review_worksheet(first)}
    if args.second:
        report["test_retest"] = compare_extractions(first, load_json_object(args.second))
    atomic_write_json(args.output, report)
    print(json.dumps({"output": str(args.output)}, ensure_ascii=False))
    return 0
