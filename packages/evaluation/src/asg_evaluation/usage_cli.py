"""Command-line report of where the model calls of every stored run went."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from asg_core import atomic_write_csv, stories_path, use_utf8_output

from .artifacts import group_by
from .text import count_noun, format_number
from .usage_report import USAGE_FIELDS, UsageRecord, collect_usage, summarize_usage

AXES = ("agent", "stage")
AXIS_LABELS = {"agent": "agente", "stage": "etapa"}


def parser() -> argparse.ArgumentParser:
    """Build the usage report command-line parser."""
    result = argparse.ArgumentParser(
        description="Reparte llamadas, tokens y latencia de cada run por agente y etapa"
    )
    result.add_argument(
        "--stories",
        help="Directorio raíz de historias; por defecto el Stories/ del proyecto",
    )
    result.add_argument(
        "--csv",
        help="Escribe una fila por run, etapa y agente en este archivo CSV",
    )
    result.add_argument(
        "--group",
        choices=(*AXES, "all"),
        default="all",
        help="Eje del reparto; 'all' da los dos (por defecto: all)",
    )
    result.add_argument(
        "--all-status",
        action="store_true",
        help="Incluye también las ejecuciones que no terminaron",
    )
    return result


def render(label: str, records: Sequence[UsageRecord], axis: str) -> str:
    """Render one approach's measured runs split along one axis, as aligned text."""
    measured = [record for record in records if record.rows is not None]
    missing = len(records) - len(measured)
    lines = [
        f"\n{label} por {AXIS_LABELS[axis]}  "
        f"({count_noun(len(measured), 'run medido', 'runs medidos')}, "
        f"{count_noun(missing, 'no medido', 'no medidos')})\n"
    ]
    if not measured:
        lines.append("    no medido: ningún run de este grupo registra el agente de cada llamada")
        return "\n".join(lines)
    lines.append(
        f"    {AXIS_LABELS[axis]:<24}{'llamadas':>10}{'% llam.':>9}{'intentos':>10}"
        f"{'fallidos':>10}{'tokens':>11}{'latencia s':>12}{'espera s':>10}"
    )
    for row in summarize_usage(measured, axis):
        share = None if row["call_share"] is None else 100 * row["call_share"]
        lines.append(
            f"    {row[axis]:<24}{row['calls']:>10}{format_number(share, 1):>9}"
            f"{row['attempts']:>10}{row['failed_attempts']:>10}{row['tokens']:>11}"
            f"{format_number(row['latency_seconds'], 1):>12}"
            f"{format_number(row['wait_seconds'], 1):>10}"
        )
    return "\n".join(lines)


def write_csv(path: Path, records: Sequence[UsageRecord]) -> None:
    """Write one row per run, stage and agent; a run without agents gets one empty row."""
    columns = ("run_id", "approach", "generator_version", "status", "stage", "agent", *USAGE_FIELDS)
    rows = []
    for record in records:
        head = [record.run_id, record.approach, record.generator_version, record.status]
        if record.rows is None:
            rows.append([*head, "", "", *([""] * len(USAGE_FIELDS))])
            continue
        rows.extend(
            [*head, row["stage"], row["agent"], *(row[name] for name in USAGE_FIELDS)]
            for row in record.rows
        )
    atomic_write_csv(path, columns, rows)


def main(argv: list[str] | None = None) -> int:
    """Run the usage report entry point."""
    use_utf8_output()
    args = parser().parse_args(argv)
    stories_root = Path(args.stories) if args.stories else stories_path()

    records = collect_usage(stories_root)
    selected = [record for record in records if args.all_status or record.status == "completed"]
    print(
        f"{count_noun(len(records), 'run', 'runs')} con registro de llamadas en {stories_root}, "
        f"{len(selected)} en el informe"
    )
    if not selected:
        print("No hay runs que resumir todavía.")
        return 0

    if args.csv:
        destination = Path(args.csv)
        write_csv(destination, selected)
        print(f"CSV escrito en {destination}")

    axes = AXES if args.group == "all" else (args.group,)
    for label, group in group_by(selected, lambda record: record.approach).items():
        for axis in axes:
            print(render(label, group, axis))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
