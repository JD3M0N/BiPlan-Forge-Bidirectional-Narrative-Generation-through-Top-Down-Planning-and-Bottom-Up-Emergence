"""Run an experiment matrix in series under the quota, with a manifest that survives a stop."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shlex
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from asg_core import atomic_write_json, use_utf8_output

from ..generator import StoryGenerator
from ..options import GenerationOptions
from ..runtime.config import load_settings
from ..runtime.errors import ASGError, GeminiBillingQuotaError, ProviderDailyQuotaError
from ..runtime.provider import provider_from_settings
from .baseline import generate_baseline
from .budget import average_story, preflight, slot_spending
from .generate import build_options, request_problem
from .generate import parser as generate_parser

BASELINE_COMMAND = "asg-baseline"
STOPPING_ERRORS = (ProviderDailyQuotaError, GeminiBillingQuotaError)
SEEDS_FILE = "semillas.json"
CATALOG_FILE = "prompts.md"
DONE = "completed"


@dataclass
class Unit:
    """One run of the matrix: a cell, a work and a repetition."""

    id: str
    cell: str
    work: str
    marker: str
    repetition: int
    kind: str
    flags: list[str]
    source: str | None
    mode: str | None
    prompt: str
    cost: tuple[int, int]
    options: GenerationOptions | None = None
    args: argparse.Namespace | None = field(default=None, repr=False)


def read_prompt(catalog: str, marker: str) -> str:
    """Return the prompt text between a marker's START and END comments in the catalog."""
    found = re.search(
        rf"<!--\s*{re.escape(marker)}_START\s*-->(.*?)<!--\s*{re.escape(marker)}_END\s*-->",
        catalog,
        flags=re.DOTALL,
    )
    if not found or not found.group(1).strip():
        raise ValueError(f"el catálogo no tiene el marcador {marker}.")
    return found.group(1).strip()


def read_cells(path: Path) -> list[dict[str, str]]:
    """Read the matrix rows that describe a cell, skipping the totals row."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if row["celda"] and row["celda"] != "TOTAL" and row["formato"]]


def _row_units(row: dict[str, str], catalog: str) -> list[Unit]:
    """Expand one cell into its units; raise ValueError for a row that cannot be read."""
    baseline = row["flags"].strip() == BASELINE_COMMAND
    source_cell, _, mode = row["desde"].strip().partition(":")
    if row["desde"].strip() and mode not in ("plan", "narrate"):
        raise ValueError(f"{row['celda']}: «desde» debe ser CELDA:plan o CELDA:narrate.")
    cost = (int(row["llamadas_principal_unidad"] or 0), int(row["llamadas_funcion_unidad"] or 0))
    units = []
    for marker in filter(None, (m.strip() for m in row["obras"].split(";"))):
        work = re.match(r"PROMPT_(\d+)_", marker)
        if not work:
            raise ValueError(f"{row['celda']}: marcador {marker!r} sin número de obra.")
        for repetition in range(1, int(row["repeticiones"]) + 1):
            suffix = f"{work.group(1)}/r{repetition}"
            units.append(
                Unit(
                    id=f"{row['celda']}/{suffix}",
                    cell=row["celda"],
                    work=work.group(1),
                    marker=marker,
                    repetition=repetition,
                    kind="baseline" if baseline else row["formato"],
                    flags=[] if baseline else shlex.split(row["flags"]),
                    source=f"{source_cell}/{suffix}" if mode else None,
                    mode=mode or None,
                    prompt=read_prompt(catalog, marker),
                    cost=cost,
                )
            )
    return units


def _prepare(unit: Unit, settings) -> str | None:
    """Resolve a unit's options from its flags; say why it cannot run, or None."""
    unit.args = generate_parser().parse_args(
        [*unit.flags, *([] if unit.source else [unit.prompt]), "--no-audio"]
    )
    if unit.mode == "plan":
        unit.args.plan_from = Path("fuente")
    elif unit.mode == "narrate":
        unit.args.narrate_from = Path("fuente")
    try:
        unit.options = build_options(unit.args, settings)
    except (ValueError, TypeError) as exc:
        return str(exc)
    return request_problem(unit.args, unit.options, "" if unit.source else unit.prompt)


def expand(cells: Iterable[dict[str, str]], catalog: str, settings) -> tuple[list[Unit], list[str]]:
    """Turn the cells into units (cell x work x repetition) and list what cannot run."""
    units: list[Unit] = []
    problems: list[str] = []
    for row in cells:
        try:
            units += _row_units(row, catalog)
        except ValueError as exc:
            problems.append(str(exc))
    for unit in units:
        problem = None if unit.kind == "baseline" else _prepare(unit, settings)
        if problem:
            problems.append(f"{unit.id}: {problem}")
    sources = {unit.id for unit in units}
    problems += [
        f"{unit.id}: su fuente {unit.source} no está en la matriz."
        for unit in units
        if unit.source and unit.source not in sources
    ]
    return units, problems


def select(
    units: list[Unit],
    cells: list[str] | None,
    works: list[str] | None,
    repetitions: list[int] | None,
) -> list[Unit]:
    """Keep the units of the cells, works and repetitions asked for; no filter keeps all."""
    return [
        unit
        for unit in units
        if (not cells or unit.cell in cells)
        and (not works or unit.work in works)
        and (not repetitions or unit.repetition in repetitions)
    ]


def _stored(path: Path, root: Path) -> str:
    """Write a run path relative to the project root when it lies inside it."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _resolve(text: str, root: Path) -> Path:
    """Turn a stored run path back into a path."""
    return root / text


def read_manifest(path: Path) -> dict:
    """Read the manifest, or start an empty one."""
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"units": {}}


def read_seeds(path: Path) -> dict[str, str]:
    """Read the runs that already exist and stand for a unit of the matrix."""
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def check_seed(unit: Unit, run: Path) -> str | None:
    """Say why an existing run is not this unit's, or None when it matches."""
    try:
        metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
        request = json.loads((run / "request.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"{run} no tiene metadata.json y request.json legibles."
    if metadata.get("status") != DONE:
        return f"{run} no está completo."
    if not unit.source and request.get("original_prompt") != unit.prompt:
        return f"el prompt de {run} no es el de {unit.marker}."
    if unit.kind == "baseline":
        return (
            None if metadata.get("story_format") == "baseline" else f"{run} no es una línea base."
        )
    try:
        recorded = GenerationOptions.model_validate_json(
            (run / "generation_options.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return f"{run} no tiene generation_options.json válido."
    if recorded != unit.options:
        return f"las opciones de {run} no son las de la celda {unit.cell}."
    return None


def _now() -> str:
    """Return the current UTC time as ISO text."""
    return datetime.now(UTC).isoformat()


def _unit_entry(unit: Unit) -> dict:
    """Describe a unit as the manifest records it."""
    return {
        "celda": unit.cell,
        "obra": unit.work,
        "repeticion": unit.repetition,
        "tipo": unit.kind,
        "fuente": unit.source,
        "modo_fuente": unit.mode,
        "opciones": unit.options.model_dump(mode="json") if unit.options else None,
        "estado": "pendiente",
        "run": None,
        "fallidos": [],
    }


def _save(path: Path, manifest: dict) -> None:
    """Write the manifest atomically."""
    manifest["actualizado"] = _now()
    atomic_write_json(path, manifest)


def _fresh_dir(parent: Path, name: str) -> Path:
    """Return a directory name under the parent that does not exist yet."""
    candidate, number = parent / name, 2
    while candidate.exists():
        candidate = parent / f"{name}-b{number}"
        number += 1
    return candidate


def _spending(settings) -> dict[str, int]:
    """Return how many requests each model has left today; absent when it has no cap."""
    left: dict[str, int] = {}
    for entry, used, _, until in slot_spending(settings, datetime.now(UTC)):
        cap = entry.slot.max_requests
        if cap:
            left[entry.slot.model] = left.get(entry.slot.model, 0) + (
                0 if until else max(0, cap - used)
            )
    return left


def dry_run(
    pending: list[Unit], settings, *, out: Callable[[str], None] = print
) -> tuple[int, int]:
    """Print what the pending units cost against what is left today; spend nothing."""
    by_cell: dict[str, list[Unit]] = {}
    for unit in pending:
        by_cell.setdefault(unit.cell, []).append(unit)
    main = function = 0
    out(f"{'celda':<6}{'unidades':>9}{'principal':>11}{'función':>9}  referencia")
    for cell, items in by_cell.items():
        principal, staged = sum(u.cost[0] for u in items), sum(u.cost[1] for u in items)
        main, function = main + principal, function + staged
        # A narration replay costs about what a narrative run does (see generate.main).
        fmt = "narrative" if items[0].mode == "narrate" else items[0].kind
        recent = average_story(settings.output_root, None if fmt == "baseline" else fmt)
        note = f"media reciente de {fmt}: {recent[0]} llamadas ({recent[2]} runs)" if recent else ""
        out(f"{cell:<6}{len(items):>9}{principal:>11}{staged:>9}  {note}")
    out(f"{'total':<6}{len(pending):>9}{main:>11}{function:>9}")
    left = _spending(settings)
    stage_model = settings.effective_stage_model
    for label, need, model in (
        ("principal", main, settings.model),
        ("función", function, stage_model),
    ):
        if model in left:
            out(f"Quedan hoy en {model} ({label}): {left[model]} de {need} necesarias.")
        else:
            out(f"{model} ({label}): sin tope conocido; necesarias {need}.")
    return main, function


def run_unit(
    unit: Unit,
    entry: dict,
    manifest: dict,
    manifest_path: Path,
    *,
    root: Path,
    settings,
    provider,
    out: Callable[[str], None],
) -> None:
    """Run one unit and record how it ended; quota errors are re-raised to stop the matrix."""
    created: list[Path] = []
    entry.update(estado="running", inicio=_now(), error=None)
    _save(manifest_path, manifest)
    try:
        if unit.kind == "baseline":
            parent = settings.output_root.parent / "Baseline"
            parent.mkdir(parents=True, exist_ok=True)
            directory = _fresh_dir(parent, f"{unit.work}-linea-base-{unit.repetition}")
            created.append(directory)
            generate_baseline(provider, unit.prompt, directory, model=settings.model)
        else:
            generator = StoryGenerator.from_options(provider, settings.output_root, unit.options)
            callbacks = {"on_run_created": created.append}
            if unit.mode:
                source = _resolve(manifest["units"][unit.source]["run"], root)
                call = (
                    generator.generate_from_plan
                    if unit.mode == "plan"
                    else generator.generate_from_performance
                )
                call(source, **callbacks)
            else:
                generator.generate(unit.prompt, **callbacks)
        entry.update(estado=DONE, run=_stored(created[-1], root), fin=_now())
    except BaseException as exc:
        if created:
            entry["run"] = _stored(created[-1], root)
        entry.update(
            estado="failed",
            fin=_now(),
            error="interrumpida" if isinstance(exc, KeyboardInterrupt) else str(exc),
        )
        raise
    finally:
        _save(manifest_path, manifest)
    out(f"  {unit.id}: {entry['estado']} → {entry['run']}")


def adopt_seeds(units: list[Unit], entries: dict, path: Path, root: Path) -> str | None:
    """Mark the units that already have a run as completed; say why a seed does not fit."""
    for unit_id, text in read_seeds(path).items():
        unit = next((u for u in units if u.id == unit_id), None)
        if unit is None or entries[unit_id]["estado"] == DONE:
            continue
        reason = check_seed(unit, _resolve(text, root))
        if reason:
            return f"la semilla de {unit_id} no coincide: {reason}"
        entries[unit_id].update(estado=DONE, run=text, semilla=True)
    return None


def budget_format(unit: Unit) -> str:
    """Return the story format whose average cost the preflight should use for a unit."""
    if unit.kind == "baseline":
        return "baseline"
    # A narration replay costs about what a narrative run does (see generate.main).
    return "narrative" if unit.mode == "narrate" else unit.options.story_format.value


def run_pending(
    pending: list[Unit],
    manifest: dict,
    manifest_path: Path,
    *,
    root: Path,
    settings,
    provider,
    check: Callable[[object, str], str | None],
    out: Callable[[str], None],
) -> int:
    """Run the pending units in order; return 0, 1 (failed or blocked) or 3 (quota)."""
    entries = manifest["units"]
    failed = blocked = 0
    for unit in pending:
        if unit.source and entries[unit.source]["estado"] != DONE:
            out(f"  {unit.id}: bloqueada, su fuente {unit.source} no está completa.")
            blocked += 1
            continue
        refusal = check(settings, budget_format(unit))
        if refusal:
            print(f"Error: no cabe en la cuota de hoy: {refusal}", file=sys.stderr)
            _save(manifest_path, manifest)
            return 3
        entry = entries[unit.id]
        if entry["run"]:
            entry["fallidos"].append(entry["run"])
        try:
            run_unit(
                unit,
                entry,
                manifest,
                manifest_path,
                root=root,
                settings=settings,
                provider=provider,
                out=out,
            )
        except STOPPING_ERRORS as exc:
            print(f"Error: cuota agotada en {unit.id}: {exc}", file=sys.stderr)
            return 3
        except (ASGError, OSError, ValueError) as exc:
            print(f"Error en {unit.id}: {exc}", file=sys.stderr)
            failed += 1
    done = len(pending) - failed - blocked
    out(f"Hecho: {done} completas, {failed} fallidas, {blocked} bloqueadas.")
    return 1 if failed or blocked else 0


def execute(
    matrix: Path,
    settings,
    *,
    manifest_path: Path | None = None,
    cells: list[str] | None = None,
    works: list[str] | None = None,
    repetitions: list[int] | None = None,
    dry: bool = False,
    provider_factory: Callable[[], object] | None = None,
    check: Callable[[object, str], str | None] = preflight,
    root: Path | None = None,
    out: Callable[[str], None] = print,
) -> int:
    """Run (or cost) the selected units of a matrix; return the exit code."""
    root = root or settings.output_root.parent.parent
    manifest_path = manifest_path or root / "Evaluations" / "horizontal" / (
        f"manifiesto-{matrix.stem}.json"
    )
    catalog = (matrix.parent / CATALOG_FILE).read_text(encoding="utf-8")
    units, problems = expand(read_cells(matrix), catalog, settings)
    if problems:
        for problem in problems:
            print(f"Error: {problem}", file=sys.stderr)
        return 2
    manifest = read_manifest(manifest_path)
    manifest.setdefault("matriz", matrix.name)
    entries = manifest["units"]
    for unit in units:
        entries.setdefault(unit.id, _unit_entry(unit))
    refusal = adopt_seeds(units, entries, matrix.parent / SEEDS_FILE, root)
    if refusal:
        print(f"Error: {refusal}", file=sys.stderr)
        return 2
    chosen = select(units, cells, works, repetitions)
    pending = [unit for unit in chosen if entries[unit.id]["estado"] != DONE]
    if dry:
        dry_run(pending, settings, out=out)
        return 0
    if not pending:
        out("Nada pendiente: las unidades elegidas ya están completas.")
        _save(manifest_path, manifest)
        return 0
    _save(manifest_path, manifest)
    provider = (provider_factory or (lambda: provider_from_settings(settings)))()
    return run_pending(
        pending,
        manifest,
        manifest_path,
        root=root,
        settings=settings,
        provider=provider,
        check=check,
        out=out,
    )


def parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    result = argparse.ArgumentParser(
        description="Lanza una matriz de experimentos en serie, con cuota y manifiesto"
    )
    result.add_argument("matriz", type=Path, help="CSV de la matriz (junto a prompts.md)")
    result.add_argument(
        "--dry-run", action="store_true", help="Cuenta las llamadas pendientes y no gasta cuota"
    )
    result.add_argument("--celdas", help="Celdas a lanzar, separadas por comas (M01,M03)")
    result.add_argument("--obras", help="Obras a lanzar, separadas por comas (01,03)")
    result.add_argument("--repeticiones", help="Repeticiones a lanzar, separadas por comas (1)")
    result.add_argument(
        "--manifest",
        type=Path,
        help="Manifiesto JSON; por defecto Evaluations/horizontal/manifiesto-<matriz>.json",
    )
    return result


def _split(text: str | None) -> list[str] | None:
    """Split a comma-separated flag, None when it was not given."""
    return [part.strip() for part in text.split(",") if part.strip()] if text else None


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entry point."""
    use_utf8_output()
    args = parser().parse_args(argv)
    try:
        settings = load_settings(require_api_key=not args.dry_run)
        repetitions = [int(n) for n in _split(args.repeticiones) or []]
        return execute(
            args.matriz,
            settings,
            manifest_path=args.manifest,
            cells=_split(args.celdas),
            works=_split(args.obras),
            repetitions=repetitions or None,
            dry=args.dry_run,
        )
    except (ASGError, OSError, ValueError, KeyboardInterrupt) as exc:
        message = exc.public_message() if isinstance(exc, ASGError) else str(exc) or "cancelada"
        print(f"\nError: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
