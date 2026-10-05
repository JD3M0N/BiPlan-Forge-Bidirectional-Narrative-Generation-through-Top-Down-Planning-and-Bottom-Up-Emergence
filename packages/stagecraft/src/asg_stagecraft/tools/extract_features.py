"""Provider-backed extraction adapter; evaluation itself never imports the generator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from asg_core import use_utf8_output
from asg_evaluation.features import extract_features
from asg_evaluation.study import StudyRepository

from ..runtime.config import load_settings
from ..runtime.provider import provider_from_settings


def main(argv: list[str] | None = None) -> int:
    """Extract one run, a corpus or frozen study texts with resumable checkpoints."""
    parser = argparse.ArgumentParser(
        description="Extraer rasgos con citas verificadas (consume cuota)"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--root", type=Path)
    source.add_argument("--study", type=Path)
    parser.add_argument("--selection", choices=("core", "all"), default="core")
    parser.add_argument(
        "--force", action="store_true", help="Repetir incluso una extracción compatible"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    use_utf8_output()
    try:
        sources = _sources(args)
        if args.dry_run:
            print(
                f"{len(sources)} textos; núcleo: ~3 llamadas por texto, "
                "más reparaciones si hacen falta."
            )
            return 0
        settings = load_settings()
        provider = provider_from_settings(settings)
        incomplete = False
        for text, output in sources:
            report = extract_features(
                text,
                provider,
                model=settings.model,
                output=output,
                selection=args.selection,
                force=args.force,
            )
            print(f"{output}: {'completa' if report['complete'] else 'incompleta'}")
            incomplete = incomplete or not report["complete"]
        return int(incomplete)
    except Exception as exc:
        print(
            f"Extracción interrumpida ({type(exc).__name__}); los lotes completos están guardados.",
            file=sys.stderr,
        )
        return 1


def _sources(args) -> list[tuple[str, Path]]:
    """Choose original run texts or immutable study snapshots, never generated substitutes."""
    if args.study:
        if not args.study.is_file():
            raise ValueError("No existe el estudio.")
        repository = StudyRepository(args.study)
        if repository.info()["snapshot"] is None:
            raise ValueError("Primero congela el conjunto del estudio.")
        return [
            (s["text"], args.study.parent / "features" / f"{s['id']}.json")
            for s in repository.export()["stories"]
        ]
    paths = (
        [args.root / "story.md"]
        if (args.root / "story.md").is_file()
        else sorted(args.root.rglob("story.md"))
    )
    return [(p.read_text(encoding="utf-8"), p.parent / "features" / "features.json") for p in paths]
