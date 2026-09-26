"""Command-line report over every stored performance."""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections.abc import Sequence
from pathlib import Path

from asg_core import atomic_write_text, find_project_root

from .simulation_report import (
    SIMULATION_COLUMNS,
    SIMULATION_FIELDS,
    SIMULATION_GROUPINGS,
    SimulationRecord,
    SimulationSummary,
    collect_simulations,
    simulation_row,
    summarize_simulations,
)
from .text import count_noun, format_number

SUMMARY_AXES = ("voice", "memory", "profile", "version", "voice-memory")
# Fields that read as a proportion get more decimals; the rest are counts or averages.
RATIO_FIELDS = frozenset(
    {
        "beat_completion_ratio",
        "repetition_ratio",
        "mean_self_similarity",
        "script_echo",
        "dialogue_survival",
    }
)


def parser() -> argparse.ArgumentParser:
    """Build the simulation report command-line parser."""
    result = argparse.ArgumentParser(
        description="Resume las funciones representadas y las agrupa por sus ejes"
    )
    result.add_argument(
        "--stories",
        help="Directorio raíz de historias; por defecto el Stories/ del proyecto",
    )
    result.add_argument(
        "--csv",
        help="Escribe una fila por función en este archivo CSV",
    )
    result.add_argument(
        "--group",
        choices=(*SIMULATION_GROUPINGS, "all"),
        default="all",
        help="Eje de agregación; 'all' recorre todos menos story (por defecto: all)",
    )
    result.add_argument(
        "--all-status",
        action="store_true",
        help="Incluye también las funciones de ejecuciones que no terminaron",
    )
    return result


def render(summaries: Sequence[SimulationSummary], axis: str) -> str:
    """Render one grouped summary as aligned text."""
    lines = [f"\nAgrupado por {axis}\n"]
    for summary in summaries:
        lines.append(f"  {summary.label}  ({count_noun(summary.runs, 'función', 'funciones')})")
        lines.append(f"    {'cifra':<28}{'media':>10}{'mediana':>10}")
        for name in SIMULATION_FIELDS:
            mean, middle = summary.values[name]
            digits = 4 if name in RATIO_FIELDS else 2
            lines.append(
                f"    {name:<28}{format_number(mean, digits):>10}"
                f"{format_number(middle, digits):>10}"
            )
        lines.append("")
    return "\n".join(lines)


def write_csv(path: Path, records: Sequence[SimulationRecord]) -> None:
    """Write one row per performance, atomically, in the declared column order."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(SIMULATION_COLUMNS)
    writer.writerows(simulation_row(record) for record in records)
    atomic_write_text(path, buffer.getvalue())


def main(argv: list[str] | None = None) -> int:
    """Run the simulation report entry point."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    stories_root = Path(args.stories) if args.stories else find_project_root() / "Stories"

    records = collect_simulations(stories_root)
    selected = [
        record
        for record in records
        if args.all_status or record.status in ("completed", "desconocido")
    ]
    print(
        f"{count_noun(len(records), 'función', 'funciones')} en {stories_root}, "
        f"{len(selected)} en el informe"
    )
    if not selected:
        print("No hay funciones que resumir todavía.")
        return 0

    if args.csv:
        destination = Path(args.csv)
        write_csv(destination, selected)
        print(f"CSV escrito en {destination}")

    axes = SUMMARY_AXES if args.group == "all" else (args.group,)
    for axis in axes:
        print(render(summarize_simulations(selected, SIMULATION_GROUPINGS[axis]), axis))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
