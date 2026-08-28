"""Create a neutral side-by-side review sheet for two generated story runs."""

from __future__ import annotations

import argparse
import html
from pathlib import Path


def build_comparison(baseline: Path, candidate: Path, output: Path) -> Path:
    """Build comparison."""
    baseline_story = baseline / "story.md" if baseline.is_dir() else baseline
    candidate_story = candidate / "story.md" if candidate.is_dir() else candidate
    left = baseline_story.read_text(encoding="utf-8")
    right = candidate_story.read_text(encoding="utf-8")
    document = f"""<!doctype html>
<html lang="es"><meta charset="utf-8"><title>Comparación ciega de historias</title>
<style>body{{font-family:system-ui;margin:2rem}}main{{display:grid;grid-template-columns:1fr 1fr;gap:2rem}}
article{{white-space:pre-wrap;line-height:1.55;border:1px solid #ccc;padding:1.5rem}}
textarea{{width:100%;min-height:8rem}}@media(max-width:900px){{main{{grid-template-columns:1fr}}}}</style>
<h1>Comparación narrativa</h1>
<p>Evalúa creatividad, engagement, naturalidad, causalidad y sensación de plantilla antes de revelar qué versión es cada una.</p>
<main><section><h2>Historia A</h2><article>{html.escape(left)}</article></section>
<section><h2>Historia B</h2><article>{html.escape(right)}</article></section></main>
<h2>Notas</h2><textarea placeholder="Preferencia y razones..."></textarea></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    return output


def main() -> int:
    """Run the command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Compara visualmente dos ejecuciones o archivos story.md"
    )
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, default=Path("story-comparison.html"))
    args = parser.parse_args()
    print(build_comparison(args.baseline, args.candidate, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
