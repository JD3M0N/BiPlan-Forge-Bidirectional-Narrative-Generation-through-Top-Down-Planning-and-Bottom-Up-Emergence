"""Command-line report over every stored performance."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from asg_core import atomic_write_csv, stories_path, use_utf8_output

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

SUMMARY_AXES = ("voice", "memory", "profile", "version", "voice-memory", "mode")
# Fields that read as a proportion get more decimals; the rest are counts or averages.
RATIO_FIELDS = frozenset(
    {
        "beat_completion_ratio",
        "repetition_ratio",
        "action_repetition_ratio",
        "thought_ratio",
        "mean_self_similarity",
        "script_echo",
        "compression_ratio",
        "dialogue_survival",
        "context_coverage",
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
        "--cost-csv",
        help="Escribe coste por run, etapa, agente y modelo en un CSV independiente",
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
    atomic_write_csv(path, SIMULATION_COLUMNS, (simulation_row(record) for record in records))


def main(argv: list[str] | None = None) -> int:
    """Run the simulation report entry point."""
    use_utf8_output()
    args = parser().parse_args(argv)
    stories_root = Path(args.stories) if args.stories else stories_path()

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
    if args.cost_csv:
        destination = Path(args.cost_csv)
        columns = ("run_id", "stage", "agent", "model", "calls", "tokens", "latency_seconds")
        atomic_write_csv(
            destination,
            columns,
            (
                [record.run_id, *[cost[name] for name in columns[1:]]]
                for record in selected
                for cost in record.costs
            ),
        )
        print(f"CSV de costes escrito en {destination}")

    axes = SUMMARY_AXES if args.group == "all" else (args.group,)
    for axis in axes:
        print(render(summarize_simulations(selected, SIMULATION_GROUPINGS[axis]), axis))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
