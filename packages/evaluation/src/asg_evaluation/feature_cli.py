"""Export uniform feature tables and observational horizontal summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asg_core import atomic_write_csv, atomic_write_json, use_utf8_output

from .catalog import catalog
from .feature_report import horizontal_report, read_features


def main(argv: list[str] | None = None) -> int:
    """Report recorded features without calling a language model."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Tabla de rasgos por historia")
    parser.add_argument("root", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--horizontal", type=Path)
    parser.add_argument("--axis", default="C02")
    args = parser.parse_args(argv)
    paths = (
        [args.root / "story.md"]
        if (args.root / "story.md").is_file()
        else sorted(args.root.rglob("story.md"))
    )
    rows, errors = [], []
    for path in paths:
        try:
            rows.append(read_features(path.parent))
        except (OSError, ValueError, TypeError) as exc:
            errors.append({"story": str(path.parent), "error": type(exc).__name__})
    if args.json:
        atomic_write_json(args.json, {"stories": rows, "errors": errors})
    if args.csv:
        fields = list(catalog())
        columns = ["story", "run_id", *fields, *(f"{key}_status" for key in fields)]
        atomic_write_csv(
            args.csv,
            columns,
            [
                [
                    row["story"],
                    row["run_id"],
                    *[_csv_value(row["features"][k]["value"]) for k in fields],
                    *[row["features"][k]["status"] for k in fields],
                ]
                for row in rows
            ],
        )
    if args.horizontal:
        atomic_write_json(args.horizontal, horizontal_report(rows, args.axis))
    print(json.dumps({"stories": len(rows), "errors": errors}, ensure_ascii=False))
    return int(bool(errors))


def _csv_value(value):
    """Keep scalar CSV values and encode structured observations without Python repr."""
    return json.dumps(value, ensure_ascii=False) if isinstance(value, list | dict) else value


if __name__ == "__main__":
    sys.exit(main())
