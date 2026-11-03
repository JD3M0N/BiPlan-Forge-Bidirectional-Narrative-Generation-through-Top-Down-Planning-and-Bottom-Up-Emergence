"""Human reports, reproducible judge training and post-hoc corpus ranking."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from asg_core import atomic_write_json, atomic_write_text, use_utf8_output

from .artifacts import load_json_object
from .catalog import catalog, prompt_work
from .feature_report import read_features, study_extractions
from .judge import perturbation_report, rank_features, train_judge
from .pairing import original_prompt
from .preferences import human_report
from .study import StudyRepository


def load_study_features(repository: StudyRepository) -> dict:
    """Read feature sidecars belonging to the frozen study's own text snapshots."""
    return {
        s["id"]: load_json_object(repository.path.parent / "features" / f"{s['id']}.json")
        for s in repository.export()["stories"]
    }


def human_main(argv: list[str] | None = None) -> int:
    """Write three human rankings, reader agreement and clustered intervals."""
    parser = argparse.ArgumentParser(description="Informe de preferencias humanas")
    parser.add_argument("db", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=1000)
    args = parser.parse_args(argv)
    use_utf8_output()
    try:
        repository = _repository(args.db)
        report = human_report(repository.export(), bootstrap=args.bootstrap)
        atomic_write_json(args.output, report)
        print(args.output)
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def train_main(argv: list[str] | None = None) -> int:
    """Train on study snapshots and save a transparent JSON model, never executable pickle."""
    parser = argparse.ArgumentParser(description="Aprender las preferencias del estudio")
    parser.add_argument("db", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--perturbations", type=Path, help="JSON con pares original/perturbed ya extraídos"
    )
    args = parser.parse_args(argv)
    use_utf8_output()
    try:
        repository = _repository(args.db)
        judge = train_judge(repository.export(), load_study_features(repository))
        if args.perturbations:
            cases = json.loads(args.perturbations.read_text(encoding="utf-8"))
            judge["perturbations"] = perturbation_report(judge, cases)
        atomic_write_json(args.output, judge)
        print(args.output)
        return int(any(c["status"] != "fitted" for c in judge["criteria"].values()))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def horizontal_units(directory: Path) -> dict[str, list[dict]]:
    """Index matrix manifests by run folder name, the only key stable across path styles."""
    units = defaultdict(list)
    for manifest in sorted(directory.glob("manifiesto-*.json")):
        for unit, entry in load_json_object(manifest).get("units", {}).items():
            if isinstance(entry, dict) and entry.get("run"):
                units[Path(entry["run"]).name].append({"manifest": str(manifest), "unit": unit})
    return units


def _value(value: object) -> str:
    """Show one feature value compactly in Markdown, structured values as JSON."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.0f}" if abs(value) >= 100 else f"{value:.3g}"
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _link(target: str, folder: Path) -> str:
    """Link relative to the worksheet, or absolute when they sit on different drives."""
    try:
        return Path(os.path.relpath(target, folder)).as_posix()
    except ValueError:
        return Path(target).resolve().as_posix()


def top_ten_sheet(report: dict, folder: Path) -> str:
    """Write the top-ten worksheet by code; strengths and weaknesses are left to the author."""
    names = {k: row["nombre"] for k, row in catalog().items()}
    profile = report["top_ten_profile"]
    lines = [
        "# Las diez primeras del ranking exploratorio",
        "",
        "> El juez del piloto no generaliza (METODOLOGIA.md §6): fuera de muestra queda por",
        "> debajo de la longitud sola. Estas diez describen **lo que premia este ajuste**, no",
        "> las mejores historias. Salen del combinado auxiliar sin las historias de",
        "> entrenamiento; el orden por longitud (T01, las más largas primero) va al lado.",
        "",
    ]
    if not report["training_marked"]:
        lines += ["**Sin `--study`: no se pudieron marcar las historias de entrenamiento.**", ""]
    lines += [
        "## Qué tienen y qué no",
        "",
        "Medianas de los rasgos núcleo (n = historias que lo midieron). Descriptivo, sin pesos.",
        "",
        "| Rasgo | Nombre | Diez | Resto | Corpus |",
        "|---|---|---|---|---|",
    ]
    for key, groups in profile.items():
        cells = [
            f"{_value(groups[g]['median'])} (n={groups[g]['n']})"
            for g in ("top_ten", "rest", "corpus")
        ]
        lines.append(f"| {key} | {names.get(key, key)} | " + " | ".join(cells) + " |")
    lines.append("")
    for i, item in enumerate(report["top_ten"], 1):
        p = item["positions"]
        work = item["work"] or "fuera del catálogo"
        lines += [
            f"## {i}. {item['run_id']}",
            "",
            f"- Ruta: `{item['story']}`",
            f"- Formato y versión: {item['format']} · pipeline {item['pipeline_version']}"
            f" · generador {item['generator_version']} · obra {work}",
            f"- Marcas: {', '.join(item['marks']) or 'ninguna'}",
            f"- Puestos: H01 {p['H01']} · H02 {p['H02']} · H03 {p['H03']}"
            f" · combinado {p['combined']} · longitud {p['length']}",
        ]
        for ref in item["horizontal"]:
            lines.append(
                f"- Análisis horizontal: [{ref['unit']}]({_link(ref['manifest'], folder)})"
            )
        lines += ["", "| Rasgo | Nombre | Valor | Mediana del corpus |", "|---|---|---|---|"]
        for key, value in item["features"].items():
            median = profile[key]["corpus"]["median"]
            lines.append(f"| {key} | {names.get(key, key)} | {_value(value)} | {_value(median)} |")
        lines += ["", "Configuración, proceso y coste:", ""]
        lines += [
            f"- {key} {names.get(key, key)}: {_value(value)}"
            for key, value in item["context"].items()
        ] or ["- (no registrados)"]
        lines += ["", "- Fortalezas (Josue):", "- Debilidades (Josue):", ""]
    return "\n".join(lines)


def rank_main(argv: list[str] | None = None) -> int:
    """Rank eligible corpus texts and create a qualitative top-ten worksheet."""
    parser = argparse.ArgumentParser(description="Ordenar historias con un juez congelado")
    parser.add_argument("model", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--study",
        type=Path,
        help="Reutilizar las extracciones de un estudio congelado y marcar sus historias",
    )
    parser.add_argument(
        "--horizontal",
        type=Path,
        help="Carpeta de manifiestos de la matriz; por defecto <root>/../Evaluations/horizontal",
    )
    args = parser.parse_args(argv)
    use_utf8_output()
    try:
        judge = load_json_object(args.model)
        extractions = study_extractions(args.study) if args.study else None
        training = (
            {s["text_hash"] for s in _repository(args.study).export()["stories"]}
            if args.study
            else None
        )
        units = horizontal_units(args.horizontal or args.root.parent / "Evaluations" / "horizontal")
        rows = []
        for path in sorted(args.root.rglob("story.md")):
            row = read_features(path.parent, extractions=extractions)
            row["work"] = prompt_work(original_prompt(path.parent))
            row["horizontal"] = units.get(path.parent.name, [])
            rows.append(row)
        report = rank_features(judge, rows, training=training)
        atomic_write_json(args.output, report)
        atomic_write_text(args.output.with_suffix(".md"), top_ten_sheet(report, args.output.parent))
        print(args.output)
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _repository(path: Path) -> StudyRepository:
    """Avoid creating empty studies when the operator mistypes an input path."""
    if not path.is_file():
        raise ValueError("No existe la base del estudio.")
    return StudyRepository(path)
