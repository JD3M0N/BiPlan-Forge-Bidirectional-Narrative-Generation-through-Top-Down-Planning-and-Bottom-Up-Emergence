"""Command-line report over the human evaluations stored next to each story."""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections.abc import Sequence
from pathlib import Path

from asg_core import atomic_write_text, find_project_root

from .evaluation import EVALUATION_FILENAME, METRICS
from .report import (
    GROUPINGS,
    EvaluationSummary,
    StoryEvaluations,
    collect_evaluations,
    summarize,
)
from .text import count_noun, format_number

CSV_COLUMNS = (
    "approach",
    "story",
    "run_id",
    "narrative_profile",
    "generator_version",
    "pipeline_version",
    "evaluation_index",
    "user",
    *METRICS,
)


def parser() -> argparse.ArgumentParser:
    """Build the evaluation-report command-line parser."""
    result = argparse.ArgumentParser(
        description="Resume las evaluaciones humanas guardadas junto a cada historia"
    )
    result.add_argument(
        "--stories",
        help="Directorio raíz de historias; por defecto el Stories/ del proyecto",
    )
    result.add_argument(
        "--csv",
        help="Escribe una fila por evaluación en este archivo CSV",
    )
    result.add_argument(
        "--group",
        choices=(*GROUPINGS, "all"),
        default="all",
        help="Eje de agregación; 'all' recorre todos (por defecto: all)",
    )
    return result


def _render(summary: EvaluationSummary, output: list[str]) -> None:
    """Append the table of one group to the report lines."""
    counts = f"{count_noun(summary.stories, 'historia', 'historias')}, "
    counts += count_noun(summary.evaluations, "evaluación", "evaluaciones")
    output.append(f"\n  {summary.label}  ({counts})")
    output.append(f"    {'métrica':<14}{'n':>4}{'media':>9}{'desv.':>9}{'varianza':>10}")
    for metric in METRICS:
        item = summary.metrics[metric]
        output.append(
            f"    {metric:<14}{item.count:>4}"
            f"{format_number(item.mean):>9}{format_number(item.stdev):>9}{format_number(item.variance):>10}"
        )


def _coverage(records: Sequence[StoryEvaluations], stories_root: Path) -> str:
    """Summarize how much of the corpus carries a file and real scores."""
    with_file = sum(1 for record in records if (record.directory / EVALUATION_FILENAME).is_file())
    scored = sum(1 for record in records if record.evaluations)
    return (
        f"{count_noun(len(records), 'historia', 'historias')} en {stories_root}, "
        f"{with_file} con {EVALUATION_FILENAME}, {scored} con puntuaciones"
    )


def _report(records: Sequence[StoryEvaluations], group: str) -> str:
    """Build the full textual report for the requested grouping axes."""
    axes = tuple(GROUPINGS) if group == "all" else (group,)
    lines: list[str] = []
    for axis in axes:
        lines.append(f"\nAgrupado por {axis}")
        summaries = summarize(records, key=GROUPINGS[axis])
        if not summaries:
            lines.append("  (sin evaluaciones)")
            continue
        for summary in summaries.values():
            _render(summary, lines)
    return "\n".join(lines)


def _csv_rows(records: Sequence[StoryEvaluations]) -> list[list[object]]:
    """Flatten every evaluation into one wide row per evaluation."""
    rows: list[list[object]] = []
    for record in records:
        for index, evaluation in enumerate(record.evaluations, start=1):
            rows.append(
                [
                    record.approach,
                    record.story,
                    record.run_id,
                    record.narrative_profile or "",
                    record.generator_version or "",
                    record.pipeline_version or "",
                    index,
                    evaluation["user"],
                    *(evaluation[metric] for metric in METRICS),
                ]
            )
    return rows


def _export_csv(records: Sequence[StoryEvaluations], destination: Path) -> int:
    """Write the wide evaluation table and report how many rows it holds."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    rows = _csv_rows(records)
    writer.writerows(rows)
    atomic_write_text(destination, buffer.getvalue())
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    """Run the evaluation-report entry point."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    stories_root = Path(args.stories) if args.stories else find_project_root() / "Stories"
    if not stories_root.is_dir():
        print(f"Error: no existe el directorio {stories_root}", file=sys.stderr)
        return 2
    broken: list[Path] = []

    def report_broken(directory: Path, error: ValueError) -> None:
        """Collect one unreadable story without stopping the walk."""
        broken.append(directory)
        print(f"{directory / EVALUATION_FILENAME}: {error}", file=sys.stderr)

    records = collect_evaluations(stories_root, on_error=report_broken)
    print(_coverage(records, stories_root))
    print(_report(records, args.group))
    if args.csv:
        rows = _export_csv(records, Path(args.csv))
        print(f"\nCSV escrito en {Path(args.csv)} con {rows} filas.")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
