"""Provider-backed extraction adapter; evaluation itself never imports the generator."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from asg_core import use_utf8_output
from asg_evaluation.artifacts import load_json_object
from asg_evaluation.catalog import digest
from asg_evaluation.corpus import scan
from asg_evaluation.feature_report import extraction_compatible, study_extractions
from asg_evaluation.features import extract_features, extraction_identity
from asg_evaluation.study import StudyRepository

from ..runtime.config import load_settings
from ..runtime.provider import provider_from_settings

# Measured main-model calls per text: P05.4's first pass and P07.6's runs until complete.
CALLS_PER_TEXT = (4, 36)
STATES = {
    "complete": "ya completos (0 llamadas)",
    "reused": "reutilizados del estudio (0 llamadas)",
    "resume": "incompletos que se reanudan",
    "fresh": "sin extraer",
    "other": "con otra huella (desde cero)",
}
PENDING = ("resume", "fresh", "other")


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
    parser.add_argument(
        "--elegibles", action="store_true", help="Solo los runs elegibles del ranking (asg-corpus)"
    )
    parser.add_argument(
        "--desde", type=_version, metavar="X.Y", help="Con --elegibles: pipelines >= X.Y"
    )
    parser.add_argument(
        "--reusar", type=Path, metavar="DB", help="Omitir textos ya completos en ese estudio"
    )
    parser.add_argument(
        "--limite", type=int, metavar="N", help="Como mucho N textos que necesiten llamadas"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.elegibles and not args.root:
        parser.error("--elegibles necesita --root")
    if args.desde and not args.elegibles:
        parser.error("--desde necesita --elegibles")
    if args.limite is not None and args.limite < 1:
        parser.error("--limite debe ser al menos 1")
    use_utf8_output()
    try:
        sources = _sources(args)
        settings = load_settings()
        filtered = args.elegibles or args.reusar or args.limite is not None
        if filtered or args.dry_run:
            states = _states(sources, settings.model, args)
            if args.dry_run:
                _print_plan(states, settings.model, args.limite)
                return 0
            pending = [s for s, state in zip(sources, states, strict=True) if state in PENDING]
            sources = pending[: args.limite] if args.limite is not None else pending
        provider = provider_from_settings(settings)
        incomplete = False
        for text, output in sources:
            try:
                report = extract_features(
                    text,
                    provider,
                    model=settings.model,
                    output=output,
                    selection=args.selection,
                    force=args.force,
                )
            except ValueError as exc:
                # An invalid scene partition stops this text, not the rest of the corpus.
                print(f"{output}: incompleta ({str(exc).strip()})")
                incomplete = True
                continue
            print(f"{output}: {'completa' if report['complete'] else 'incompleta'}")
            incomplete = incomplete or not report["complete"]
        return int(incomplete)
    except Exception as exc:
        print(
            f"Extracción interrumpida ({type(exc).__name__}); los lotes completos están guardados.",
            file=sys.stderr,
        )
        return 1


def _version(value: str) -> tuple[int, ...]:
    """Parse X.Y as an integer tuple so that 7.20 sorts after 7.9."""
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError:
        raise argparse.ArgumentTypeError(f"versión no válida: {value}") from None


def _sources(args) -> list[tuple[str, Path]]:
    """Choose original run texts or immutable study snapshots, never generated substitutes."""
    if args.study:
        if not args.study.is_file():
            raise ValueError("No existe el estudio.")
        repository = StudyRepository(args.study)
        if repository.info()["snapshot"] is None:
            raise ValueError("Primero abre la votación: asg-study open congela el conjunto.")
        return [
            (s["text"], args.study.parent / "features" / f"{s['id']}.json")
            for s in repository.export()["stories"]
        ]
    if args.elegibles:
        paths = _eligible_stories(args.root, args.desde)
    elif (args.root / "story.md").is_file():
        paths = [args.root / "story.md"]
    else:
        paths = sorted(args.root.rglob("story.md"))
    return [(p.read_text(encoding="utf-8"), p.parent / "features" / "features.json") for p in paths]


def _eligible_stories(root: Path, since: tuple[int, ...] | None) -> list[Path]:
    """List the stories asg-rank would order, optionally from one pipeline version on."""
    if not root.is_dir() or (root / "metadata.json").is_file():
        raise ValueError("--elegibles necesita la raíz del corpus, no un run.")
    paths = []
    for row in scan(root)["runs"]:
        if not row["eligible"]:
            continue
        if since and _version(row["pipeline_version"]) < since:
            continue
        paths.append(root / row["run"] / "story.md")
    return sorted(paths)


def _states(sources: list[tuple[str, Path]], model: str, args) -> list[str]:
    """Classify each text by the calls it needs, without creating a provider."""
    reused = study_extractions(args.reusar) if args.reusar else {}
    states = []
    for text, output in sources:
        text_hash = digest(text)
        study = reused.get(text_hash, {})
        cached = load_json_object(output)
        identity = extraction_identity(text, model, args.selection)
        if study.get("complete") and extraction_compatible(study, text_hash):
            states.append("reused")
        elif not cached:
            states.append("fresh")
        elif cached.get("identity") != identity or args.force:
            states.append("other")
        else:
            states.append("complete" if cached.get("complete") else "resume")
    return states


def _print_plan(states: list[str], model: str, limit: int | None) -> None:
    """Print totals per state and the measured cost range of the pending texts."""
    counts = Counter(states)
    pending = sum(counts[state] for state in PENDING)
    batch = min(pending, limit) if limit is not None else pending
    low, high = (batch * n for n in CALLS_PER_TEXT)
    print(f"{len(states)} textos; modelo {model}.")
    for state, label in STATES.items():
        print(f"  {label}: {counts[state]}")
    print(f"Pendientes: {pending}; en este lote: {batch}.")
    print(
        f"Coste medido: de ~{low} llamadas principales (primera pasada) "
        f"a ~{high} (reanudando hasta completar)."
    )
