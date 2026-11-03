"""Regenerate the thesis tables from the stored evaluation artifacts.

Every table is a LaTeX ``tabular`` for ``\\input`` plus a CSV with the raw values. Nothing here
calls a model or imports the generator: it reads the artifacts that ``Evaluations/`` already holds
and records which input produced each table.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from asg_core import atomic_write_csv, atomic_write_json, atomic_write_text, use_utf8_output

from .artifacts import load_json_object
from .catalog import catalog

CRITERIA = (("H01", "Creatividad"), ("H02", "Personajes"), ("H03", "Trama"))
STATUS_LABELS = {"insufficient": "insuficiente", "ok": "calculado", "fitted": "ajustado"}
CELL_LABELS = {
    "M01": "Base (valores absolutos)",
    "M03": "Narrativa desde el plan",
    "M04": "Tono sombrío",
    "M05": "Tono humorístico",
    "M06": "Visión limitada",
    "M07": "Primera persona",
}
MATRIX_NAMES = {
    "M01": "M01 Base simulada",
    "M02": "M02 Líneas base",
    "M03": "M03 Narrativa desde el plan",
    "M04": "M04 Tono sombrío",
    "M05": "M05 Tono humorístico",
    "M06": "M06 Visión limitada",
    "M07": "M07 Primera persona",
}
HAND_MADE = {
    "tab:lecturas": "docs/resumen.md (P02.1 y P02.2) y Evaluations/estudio/lecturas/",
    "tab:extractor": "packages/evaluation/METODOLOGIA.md §3, Validación del extractor",
    "tab:coste": "llm_calls.jsonl de los runs de la matriz (carpetas citadas en Experiments.tex)",
}
UNAVAILABLE = "No disponible"
FORMAT_LABELS = {
    "simulated": "simulado",
    "narrative": "narrativo",
    "baseline": "línea base",
    "script": "guion",
}
RANKING_GLOB = "ranking/ranking-*.json"
WRAPPED = r">{\raggedright\arraybackslash}p{4.8cm}"
ELIGIBLE_EXITS = frozenset(
    {"Extracción ausente u obsoleta", "Extracción incompleta", "Protocolo de extracción distinto"}
)
MATRIX_STATES = (("completed", "Completadas"), ("failed", "Fallidas"))


@dataclass(frozen=True)
class Table:
    """One regenerated table: LaTeX alignment, header, display rows and raw CSV rows."""

    name: str
    alignment: str
    header: list[str]
    rows: list[list[str]]
    raw_header: list[str]
    raw_rows: list[list[object]]


@dataclass(frozen=True)
class Spec:
    """A table name, the artifacts it needs (relative to ``Evaluations/``) and its builder."""

    name: str
    inputs: tuple[str, ...]
    build: Callable[[Path], Table]


def number(value: float | int | None, decimals: int = 2, *, signed: bool = False) -> str:
    """Format with the Spanish decimal comma, a dot for thousands and math-mode signs."""
    if value is None:
        return "---"
    text = f"{abs(value):,.{decimals}f}".translate(str.maketrans(",.", ".,"))
    sign = "-" if value < 0 else "+" if signed else ""
    return f"${sign}${text}" if sign else text


def tabular(table: Table) -> str:
    """Render a ``tabular`` with booktabs rules, ready for ``\\input``."""
    lines = [f"\\begin{{tabular}}{{{table.alignment}}}", "\\toprule"]
    lines.append(" & ".join(table.header) + " \\\\")
    lines.append("\\midrule")
    lines.extend(" & ".join(row) + " \\\\" for row in table.rows)
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    return "\n".join(lines)


def unavailable(missing: list[str]) -> Table:
    """Mark a table whose inputs are missing, naming them."""
    detail = "; ".join(missing).replace("_", "\\_")
    return Table("", "@{}l@{}", [UNAVAILABLE], [[f"Falta {detail}"]], [UNAVAILABLE], [[detail]])


def _hits(entry: dict) -> str:
    """Show accuracy with the number of correct votes, or a dash when it was not measured."""
    accuracy, tested = entry.get("accuracy"), entry.get("tested_votes")
    if accuracy is None or not tested:
        return "---"
    return f"{number(accuracy)} ({round(accuracy * tested)})"


def judge_table(evaluations: Path) -> Table:
    """Out-of-sample accuracy of the judge against chance and the length-only baseline."""
    judge = load_json_object(evaluations / "estudio-piloto-722" / "juez.json")
    header = ["Criterio", "Votos", "Juez hist.", "Juez fam.", "Long. hist.", "Long. fam.", "Azar"]
    rows, raw = [], []
    for key, label in CRITERIA:
        entry = judge.get("criteria", {}).get(key, {})
        story, family = entry.get("validation", {}), entry.get("family_validation", {})
        base = entry.get("length_baseline", {})
        parts = [story, family, base.get("by_story", {}), base.get("by_family", {})]
        chance = story.get("chance_accuracy")
        rows.append(
            [f"{label} ({key})", str(story.get("tested_votes", "---")), *map(_hits, parts)]
            + [number(chance, 1)]
        )
        raw.append([key, story.get("tested_votes"), *(p.get("accuracy") for p in parts), chance])
    names = ["criterion", "votes", "judge_story", "judge_family", "length_story", "length_family"]
    return Table(
        "juez",
        "@{}lrrrrrr@{}",
        header,
        rows,
        names + ["chance"],
        raw,
    )


def preferences_table(evaluations: Path) -> Table:
    """Coverage and agreement of the human preferences, with and without the author."""
    prefs = load_json_object(evaluations / "estudio-piloto-722" / "preferencias.json")
    header = ["Criterio", "Lectores", "Estado", "Comp.", "Acuerdo", "$\\alpha$", "Abst."]
    rows, raw = [], []
    for group, label in (("all", "todos"), ("without_author", "sin autor")):
        for key, name in CRITERIA:
            entry = prefs.get(group, {}).get(key, {})
            agreement = entry.get("agreement", {})
            status = entry.get("status", "---")
            alpha = agreement.get("krippendorff_alpha_nominal")
            rows.append(
                [
                    f"{name} ({key})",
                    label,
                    STATUS_LABELS.get(status, status),
                    str(len(entry.get("components", []))),
                    number(agreement.get("agreement")),
                    number(alpha, signed=alpha is not None),
                    str(agreement.get("abstentions", "---")),
                ]
            )
            raw.append(
                [group, key, status, len(entry.get("components", []))]
                + [agreement.get("agreement"), alpha, agreement.get("abstentions")]
            )
    raw_header = ["group", "criterion", "status", "components", "agreement", "alpha", "abstentions"]
    return Table("preferencias", "@{}llrrrrr@{}", header, rows, raw_header, raw)


def perturbation_table(evaluations: Path) -> Table:
    """Score change (perturbed minus original) for each perturbed pilot story."""
    folder = evaluations / "estudio-piloto-722"
    judge = load_json_object(folder / "juez.json")
    names = {
        story: label
        for label, story in load_json_object(folder / "protocolo.json").get("historias", {}).items()
    }
    suffixes = {"shuffled": "barajada", "no-ending": "sin desenlace"}
    cases = sorted(
        judge.get("perturbations", []),
        key=lambda c: (names.get(c["name"].partition("-")[0], c["name"]), c["name"]),
    )
    rows, raw, lowered = [], [], {key: 0 for key, _ in CRITERIA}
    for case in cases:
        story, _, kind = case["name"].partition("-")
        label = f"{names.get(story, story)} {suffixes.get(kind, kind)}"
        deltas = [case.get("criteria", {}).get(key, {}).get("delta") for key, _ in CRITERIA]
        for key, _ in CRITERIA:
            lowered[key] += bool(case.get("criteria", {}).get(key, {}).get("decreased"))
        rows.append([label, *(number(d, signed=d is not None) for d in deltas)])
        raw.append([label, *deltas])
    rows.append([f"Bajan (de {len(cases)})", *(str(lowered[key]) for key, _ in CRITERIA)])
    raw.append(["decreased", *(lowered[key] for key, _ in CRITERIA)])
    header = ["Caso", *(f"{name} ({key})" for key, name in CRITERIA)]
    return Table("perturbaciones", "@{}lrrr@{}", header, rows, ["case", "H01", "H02", "H03"], raw)


def pilot_table(evaluations: Path) -> Table:
    """Differences from the base in the horizontal pilot, for the three code-measured traits."""
    path = evaluations / "horizontal" / "piloto-03" / "horizontal.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    traits = ("T01", "T06", "T08")
    by_cell: dict[str, dict] = {}
    for record in records:
        cell = by_cell.setdefault(record["celda"], {"kind": record["tipo"], "reading": ""})
        if record["rasgo"] in traits:
            cell[record["rasgo"]] = float(record["mediana"]) if record["mediana"] else None
        if record["rasgo"] == "T01":
            cell["reading"] = record["lectura"]
    rows, raw = [], []
    for name in sorted(by_cell):
        cell = by_cell[name]
        signed = cell["kind"] != "base"
        values = [cell.get(trait) for trait in traits]
        shown = [
            number(v, 0 if trait == "T01" else 2, signed=signed and v is not None)
            for trait, v in zip(traits, values, strict=True)
        ]
        rows.append([CELL_LABELS.get(name, name), *shown, cell["reading"] or "---"])
        raw.append([name, cell["kind"], *values, cell["reading"]])
    header = ["Celda", "Palabras", "Proporción de diálogo", "Repetición de trigramas", "Lectura"]
    raw_header = ["cell", "kind", *traits, "reading"]
    return Table("piloto", "@{}lrrrl@{}", header, rows, raw_header, raw)


def matrix_table(evaluations: Path) -> Table:
    """How many matrix units each cell has, finished, failed or not generated."""
    manifest = load_json_object(evaluations / "horizontal" / "manifiesto-matriz.json")
    cells: dict[str, dict[str, int]] = {}
    for key, unit in manifest.get("units", {}).items():
        counts = cells.setdefault(key.split("/")[0], {"total": 0, "completed": 0, "failed": 0})
        counts["total"] += 1
        state = unit.get("estado")
        if state in counts:
            counts[state] += 1
    rows, raw = [], []
    for cell in sorted(cells):
        c = cells[cell]
        rest = c["total"] - c["completed"] - c["failed"]
        rows.append(
            [
                MATRIX_NAMES.get(cell, cell),
                *(str(v) for v in (c["total"], c["completed"], c["failed"], rest)),
            ]
        )
        raw.append([cell, c["total"], c["completed"], c["failed"], rest])
    totals = [sum(r[i] for r in raw) for i in range(1, 5)]
    rows.append(["Total", *map(str, totals)])
    raw.append(["total", *totals])
    header = ["Celda", "Unidades", "Completadas", "Fallidas", "Sin generar"]
    raw_header = ["cell", "units", "completed", "failed", "ungenerated"]
    return Table("matriz", "@{}lrrrr@{}", header, rows, raw_header, raw)


def _name(story: str) -> str:
    """Return the run folder of a story path written on any platform."""
    return story.replace("\\", "/").rstrip("/").rpartition("/")[2]


def _median(entry: dict) -> str:
    """Show a group median with its n; one decimal place fewer as the magnitude grows."""
    value = entry.get("median")
    if value is None:
        return "---"
    magnitude = abs(value)
    if float(value).is_integer():
        decimals = 0
    else:
        decimals = 3 if magnitude < 1 else 2 if magnitude < 10 else 1 if magnitude < 100 else 0
    return f"{number(value, decimals)} ({entry.get('n', 0)})"


def ranking_coverage_table(path: Path) -> Table:
    """How many runs were ordered, how many entered the top ten and why the rest left."""
    ranking = load_json_object(path)
    stories, excluded = ranking.get("stories", []), ranking.get("excluded", [])
    trained = sum("training" in story.get("marks", []) for story in stories)
    reasons: dict[str, int] = {}
    for item in excluded:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1
    group = {r: "Elegible que sale" for r in ELIGIBLE_EXITS}
    ranked = sorted(reasons.items(), key=lambda r: (r[0] not in ELIGIBLE_EXITS, -r[1], r[0]))
    rows = [
        ["Ordenada", "Ordenadas por el juez", str(len(stories))],
        ["Ordenada", "de ellas, del entrenamiento (fuera de las diez)", str(trained)],
        ["Ordenada", "Las diez primeras (las que haya)", str(len(ranking.get("top_ten", [])))],
        *([group.get(reason, "No elegible"), reason, str(count)] for reason, count in ranked),
    ]
    header = ["Grupo", "Situación", "Runs"]
    return Table("", "@{}llr@{}", header, rows, ["group", "situation", "runs"], rows)


def ranking_positions_table(path: Path) -> Table:
    """Every ordered story with its place in the three rankings, the combined and the length."""
    ordered = sorted(
        load_json_object(path).get("stories", []),
        key=lambda story: story.get("positions", {}).get("combined") or 99,
    )
    header = ["Historia", "Formato", "Marca", "H01", "H02", "H03", "Comb.", "Long."]
    rows, raw = [], []
    for story in ordered:
        places = story.get("positions", {})
        marks = ", ".join(
            "entrenamiento" if mark == "training" else mark for mark in story.get("marks", [])
        )
        fmt = FORMAT_LABELS.get(story.get("format"), str(story.get("format")))
        found = [places.get(key) for key in ("H01", "H02", "H03", "combined", "length")]
        rows.append([_name(story["story"]), fmt, marks or "---", *(str(p) for p in found)])
        raw.append([story["story"], story.get("format"), marks, *found])
    raw_header = ["story", "format", "marks", "H01", "H02", "H03", "combined", "length"]
    return Table("", "@{}" + WRAPPED + "llrrrrr@{}", header, rows, raw_header, raw)


def ranking_profile_table(path: Path) -> Table:
    """Core-feature medians of the top ten, the rest of the ordered corpus and all of it."""
    profile = load_json_object(path).get("top_ten_profile", {})
    names = catalog()
    header = ["Rasgo", "Nombre", "Las diez", "Resto", "Ordenadas"]
    rows, raw = [], []
    for key, groups in profile.items():
        cells = [groups.get(group, {}) for group in ("top_ten", "rest", "corpus")]
        rows.append([key, names.get(key, {}).get("nombre", key), *map(_median, cells)])
        raw.append([key, *(c.get("median") for c in cells), *(c.get("n") for c in cells)])
    raw_header = ["feature", "top_ten", "rest", "corpus", "n_top_ten", "n_rest", "n_corpus"]
    return Table("", "@{}l" + WRAPPED + "rrr@{}", header, rows, raw_header, raw)


def judge_figure(evaluations: Path) -> str:
    """Draw the out-of-sample accuracy bars of the judge and the length baseline in TikZ."""
    judge = load_json_object(evaluations / "estudio-piloto-722" / "juez.json")
    series = (
        ("Juez, por historia", ("validation",), "black!70"),
        ("Juez, por familia", ("family_validation",), "black!45"),
        ("Longitud, por historia", ("length_baseline", "by_story"), "black!20"),
        ("Longitud, por familia", ("length_baseline", "by_family"), "black!8"),
    )
    lines = [r"\begin{tikzpicture}[x=7cm, y=0.5cm, font=\small]"]
    row = 0
    for key, label in CRITERIA:
        entry = judge.get("criteria", {}).get(key, {})
        lines.append(rf"\node[anchor=west, font=\bfseries\small] at (-0.5,{-row}) {{{label}}};")
        row += 1
        for name, path, fill in series:
            data = entry
            for step in path:
                data = data.get(step, {})
            accuracy = data.get("accuracy")
            lines.append(rf"\node[anchor=east] at (-0.02,{-row}) {{{name}}};")
            if accuracy is not None:
                lines.append(
                    rf"\filldraw[fill={fill}, draw=black] (0,{-row - 0.35}) "
                    rf"rectangle ({accuracy:.4f},{-row + 0.35});"
                )
                lines.append(
                    rf"\node[anchor=west] at ({accuracy:.4f},{-row}) {{{number(accuracy)}}};"
                )
            row += 1
        row += 1
    bottom = -row + 0.5
    lines.append(rf"\draw[dashed] (0.5,0.6) -- (0.5,{bottom}) node[below] {{azar}};")
    lines.append(rf"\draw (0,0.6) -- (0,{bottom});")
    lines.extend(
        rf"\draw ({tick},{bottom}) -- ({tick},{bottom - 0.15}) "
        rf"node[below] {{{number(tick, 1)}}};"
        for tick in (0, 0.5, 1)
    )
    lines.extend([r"\end{tikzpicture}", ""])
    return "\n".join(lines)


SPECS = (
    Spec("juez", ("estudio-piloto-722/juez.json",), judge_table),
    Spec("preferencias", ("estudio-piloto-722/preferencias.json",), preferences_table),
    Spec(
        "perturbaciones",
        ("estudio-piloto-722/juez.json", "estudio-piloto-722/protocolo.json"),
        perturbation_table,
    ),
    Spec("piloto", ("horizontal/piloto-03/horizontal.csv",), pilot_table),
    Spec("matriz", ("horizontal/manifiesto-matriz.json",), matrix_table),
)


def sha256(path: Path) -> str | None:
    """Return the SHA-256 of a file, or None when it does not exist."""
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ranking_specs(relative: str) -> tuple[Spec, ...]:
    """Specs of the three ranking tables, all read from one ``asg-rank`` JSON."""

    def at(builder: Callable[[Path], Table]) -> Callable[[Path], Table]:
        """Bind a ranking builder to its file under ``Evaluations/``."""
        return lambda evaluations: builder(evaluations / relative)

    return (
        Spec("ranking_cobertura", (relative,), at(ranking_coverage_table)),
        Spec("ranking_puestos", (relative,), at(ranking_positions_table)),
        Spec("ranking_perfil", (relative,), at(ranking_profile_table)),
    )


def latest_ranking(evaluations: Path) -> str:
    """Name the newest ``ranking-<date>.json``, or the glob when none exists yet."""
    found = sorted(evaluations.glob(RANKING_GLOB))
    return found[-1].relative_to(evaluations).as_posix() if found else RANKING_GLOB


def build_all(evaluations: Path, out: Path, specs: tuple[Spec, ...]) -> dict:
    """Write every table under ``out`` and return the manifest entries by table name."""
    entries = {}
    for spec in specs:
        hashes = {name: sha256(evaluations / name) for name in spec.inputs}
        missing = [name for name, digest in hashes.items() if digest is None]
        try:
            table = unavailable(missing) if missing else spec.build(evaluations)
        except (OSError, ValueError, KeyError, TypeError) as error:
            missing = [f"{type(error).__name__} en {', '.join(spec.inputs)}"]
            table = unavailable(missing)
        tex, csv_path = out / f"{spec.name}.tex", out / f"{spec.name}.csv"
        atomic_write_text(tex, tabular(table))
        atomic_write_csv(csv_path, table.raw_header, table.raw_rows)
        entries[spec.name] = {
            "estado": "no disponible" if missing else "generada",
            "entradas": hashes,
            "salidas": {path.name: sha256(path) for path in (tex, csv_path)},
        }
    return entries


def _missing_figure(source: str) -> str:
    """Return a placeholder box that names the missing artifact."""
    return "\\fbox{" + UNAVAILABLE + ": " + source.replace("_", "\\_") + "}\n"


def build_figures(evaluations: Path, out: Path) -> dict:
    """Write the TikZ figures under ``out`` and return their manifest entries."""
    source = "estudio-piloto-722/juez.json"
    digest = sha256(evaluations / source)
    drawing = judge_figure(evaluations) if digest else _missing_figure(source)
    target = out / "juez.tex"
    atomic_write_text(target, drawing)
    return {
        "juez": {
            "estado": "generada" if digest else "no disponible",
            "entradas": {source: digest},
            "salidas": {target.name: sha256(target)},
        }
    }


def main(argv: list[str] | None = None) -> int:
    """Regenerate the thesis tables and figures from ``Evaluations`` and write the manifest."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Regenera las tablas y figuras de la tesis")
    parser.add_argument("--evaluations", type=Path, default=Path("Evaluations"))
    parser.add_argument("--tablas", type=Path, default=Path("redaccion/tablas"))
    parser.add_argument("--figuras", type=Path, default=Path("redaccion/figuras"))
    parser.add_argument(
        "--ranking", help="ranking-<fecha>.json de asg-rank, relativo a --evaluations (el último)"
    )
    parser.add_argument("--fecha", help="Fecha del manifiesto (AAAA-MM-DD); hoy por defecto")
    args = parser.parse_args(argv)
    ranking = args.ranking or latest_ranking(args.evaluations)
    tables = build_all(args.evaluations, args.tablas, SPECS + ranking_specs(ranking))
    figures = build_figures(args.evaluations, args.figuras)
    atomic_write_json(
        args.tablas / "manifiesto.json",
        {
            "comando": "asg-results",
            "version": metadata.version("asg-evaluation"),
            "fecha": args.fecha or datetime.now(UTC).date().isoformat(),
            "alcance": "tablas y figuras de la tesis regenerables desde Evaluations/",
            "tablas": tables,
            "figuras": figures,
            "a_mano": HAND_MADE,
        },
    )
    entries = {**tables, **{f"figura:{k}": v for k, v in figures.items()}}
    missing = [name for name, item in entries.items() if item["estado"] != "generada"]
    print(json.dumps({"generadas": len(entries) - len(missing), "no_disponibles": missing}))
    return int(bool(missing))


if __name__ == "__main__":
    sys.exit(main())
