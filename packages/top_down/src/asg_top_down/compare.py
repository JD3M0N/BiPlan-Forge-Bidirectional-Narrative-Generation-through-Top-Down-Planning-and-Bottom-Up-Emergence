"""Create a neutral side-by-side review sheet for two or more generated story runs."""

from __future__ import annotations

import argparse
import html
import string
from collections.abc import Sequence
from pathlib import Path


def build_comparison(runs: Sequence[Path], output: Path) -> Path:
    """Build comparison."""
    labels = string.ascii_uppercase
    stories = [run / "story.md" if run.is_dir() else run for run in runs]
    bodies = [story.read_text(encoding="utf-8") for story in stories]
    sections = "".join(
        f"<section><h2>Historia {labels[index]}</h2>"
        f"<article>{html.escape(body)}</article></section>"
        for index, body in enumerate(bodies)
    )
    document = f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><title>Comparación ciega de historias</title>
<style>body{{font-family:system-ui;margin:2rem}}main{{display:grid;grid-template-columns:repeat({len(runs)},1fr);gap:2rem}}
article{{white-space:pre-wrap;line-height:1.55;border:1px solid #ccc;padding:1.5rem}}
textarea{{width:100%;min-height:8rem}}@media(max-width:900px){{main{{grid-template-columns:1fr}}}}</style>
<h1>Comparación narrativa</h1>
<p>Evalúa creatividad, engagement, naturalidad, causalidad y sensación de plantilla
antes de revelar qué versión es cada una.</p>
<main>{sections}</main>
<h2>Notas</h2><textarea placeholder="Preferencia y razones..."></textarea></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Compara visualmente dos o más ejecuciones o archivos story.md"
    )
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("story-comparison.html"))
    args = parser.parse_args(argv)
    if len(args.runs) < 2:
        parser.error("se requieren al menos dos ejecuciones para comparar")
    print(build_comparison(args.runs, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
