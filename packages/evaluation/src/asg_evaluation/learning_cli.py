"""Human reports, reproducible judge training and post-hoc corpus ranking."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from asg_core import atomic_write_json, atomic_write_text, use_utf8_output

from .artifacts import load_json_object
from .feature_report import read_features
from .judge import perturbation_report, rank_features, train_judge
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


def rank_main(argv: list[str] | None = None) -> int:
    """Rank eligible corpus texts and create a qualitative top-ten worksheet."""
    parser = argparse.ArgumentParser(description="Ordenar historias con un juez congelado")
    parser.add_argument("model", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    use_utf8_output()
    try:
        judge = load_json_object(args.model)
        rows = [read_features(p.parent) for p in sorted(args.root.rglob("story.md"))]
        report = rank_features(judge, rows)
        atomic_write_json(args.output, report)
        lines = ["# Análisis cualitativo de las diez primeras", "", "Ranking exploratorio.", ""]
        for i, item in enumerate(report["top_ten"], 1):
            lines.extend(
                [
                    f"## {i}. {item['story']}",
                    "",
                    "- Rasgos y evidencias:",
                    "- Configuración y proceso:",
                    "- Fortalezas:",
                    "- Debilidades:",
                    "",
                ]
            )
        atomic_write_text(args.output.with_suffix(".md"), "\n".join(lines))
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
