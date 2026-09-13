"""Command-line report over the prose craft recomputed from every stored story."""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections.abc import Sequence
from pathlib import Path

from asg_core import atomic_write_text, find_project_root

from .craft_report import (
    CRAFT_COLUMNS,
    CRAFT_FIELDS,
    CRAFT_GROUPINGS,
    METRICS_FILENAME,
    CraftSummary,
    StoryCraft,
    collect_story_craft,
    craft_row,
    filter_records,
    summarize_craft,
)
from .text import count_noun, format_number

DEFAULT_MINIMUM_VERSION = "6"
SUMMARY_AXES = ("version", "profile", "version-profile", "approach", "status")


def parser() -> argparse.ArgumentParser:
    """Build the story-craft report command-line parser."""
    result = argparse.ArgumentParser(
        description="Mide la artesania de la prosa de cada historia guardada y la agrupa"
    )
    result.add_argument(
        "--stories",
        help="Directorio raíz de historias; por defecto el Stories/ del proyecto",
    )
    result.add_argument(
        "--csv",
        help="Escribe una fila por historia en este archivo CSV",
    )
    result.add_argument(
        "--group",
        choices=(*CRAFT_GROUPINGS, "all"),
        default="all",
        help="Eje de agregación; 'all' recorre todos menos story (por defecto: all)",
    )
    result.add_argument(
        "--min-version",
        default=DEFAULT_MINIMUM_VERSION,
        help=(
            "Versión mínima de generador o pipeline que entra en el informe "
            f"(por defecto: {DEFAULT_MINIMUM_VERSION}); usa 0 para no filtrar"
        ),
    )
    result.add_argument(
        "--include-unversioned",
        action="store_true",
        help="Incluye las ejecuciones que no declaran versión, como las del Bottom-Up",
    )
    result.add_argument(
        "--approach",
        help="Restringe el informe a un enfoque, por ejemplo Top-Down",
    )
    result.add_argument(
        "--all-status",
        action="store_true",
        help="Resume también las ejecuciones que no terminaron; por defecto solo entran al CSV",
    )
    return result


def _render(summary: CraftSummary, output: list[str]) -> None:
    """Append the table of one group to the report lines."""
    counts = f"{count_noun(summary.stories, 'historia', 'historias')}, "
    counts += f"{summary.without_dialogue} sin diálogo"
    output.append(f"\n  {summary.label}  ({counts})")
    header = f"{'cifra':<22}{'n':>4}{'media':>10}{'mediana':>10}{'min':>10}{'max':>10}"
    output.append(f"    {header}")
    for field in CRAFT_FIELDS:
        item = summary.stats[field]
        output.append(
            f"    {field:<22}{item.count:>4}"
            f"{format_number(item.mean):>10}{format_number(item.median):>10}"
            f"{format_number(item.minimum):>10}{format_number(item.maximum):>10}"
        )


def _coverage(
    records: Sequence[StoryCraft],
    selected: Sequence[StoryCraft],
    summarized: Sequence[StoryCraft],
    stories_root: Path,
) -> str:
    """Summarize how much of the corpus the report reaches and how much it measures."""
    with_metrics = sum(1 for record in selected if record.recorded)
    silent = sum(1 for record in selected if record.craft.dialogue_paragraphs == 0)
    return (
        f"{count_noun(len(records), 'historia', 'historias')} en {stories_root}, "
        f"{len(selected)} en el informe, {len(summarized)} en el resumen, "
        f"{with_metrics} con {METRICS_FILENAME}, {silent} sin diálogo"
    )


def _report(records: Sequence[StoryCraft], group: str) -> str:
    """Build the full textual report for the requested grouping axes."""
    axes = SUMMARY_AXES if group == "all" else (group,)
    lines: list[str] = []
    for axis in axes:
        lines.append(f"\nAgrupado por {axis}")
        summaries = summarize_craft(records, key=CRAFT_GROUPINGS[axis])
        if not summaries:
            lines.append("  (sin historias)")
            continue
        for summary in summaries.values():
            _render(summary, lines)
    return "\n".join(lines)


def _export_csv(records: Sequence[StoryCraft], destination: Path) -> int:
    """Write one row per measured story and report how many rows it holds."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CRAFT_COLUMNS)
    rows = [craft_row(record) for record in records]
    writer.writerows(rows)
    atomic_write_text(destination, buffer.getvalue())
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    """Run the story-craft report entry point."""
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

    def report_broken(path: Path, error: str) -> None:
        """Collect one unreadable artifact without stopping the walk."""
        broken.append(path)
        print(f"{path}: {error}", file=sys.stderr)

    records = collect_story_craft(stories_root, on_error=report_broken)
    selected = filter_records(
        records,
        minimum_version=args.min_version,
        approach=args.approach,
        include_unversioned=args.include_unversioned,
    )
    summarized = filter_records(
        selected, completed_only=not args.all_status, include_unversioned=True
    )
    print(_coverage(records, selected, summarized, stories_root))
    print(_report(summarized, args.group))
    if args.csv:
        rows = _export_csv(selected, Path(args.csv))
        print(f"\nCSV escrito en {Path(args.csv)} con {rows} filas.")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
