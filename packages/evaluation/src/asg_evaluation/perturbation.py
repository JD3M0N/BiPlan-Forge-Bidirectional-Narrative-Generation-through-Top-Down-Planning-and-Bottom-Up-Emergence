"""Deterministic code-made perturbations of frozen study texts for the judge control."""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

from asg_core import atomic_write_json, atomic_write_text, use_utf8_output

from .artifacts import load_json_object
from .catalog import digest
from .feature_report import _compatible
from .study import StudyRepository

SCHEMA_VERSION = 1
KINDS = ("shuffled", "no-ending")
RULES = {
    "shuffled": (
        "Capítulos «## » barajados con la semilla; sin capítulos, tercios de párrafos. "
        "El título y lo previo al primer capítulo quedan en su sitio; si el sorteo repite "
        "el orden original, se rota uno."
    ),
    "no-ending": (
        "Prefijo del texto sin el último quinto de los párrafos de cuerpo (ceil(n/5), al menos "
        "uno), cortado en un límite de párrafo y sin encabezados colgando al final."
    ),
}
_SEPARATOR = re.compile(r"\n[ \t]*\n\s*")


def blocks(text: str) -> list[tuple[int, str]]:
    """Split text into blank-line separated blocks, keeping each block's start offset."""
    result, start = [], 0
    for separator in [*_SEPARATOR.finditer(text), None]:
        chunk = text[start : separator.start() if separator else len(text)]
        if chunk.strip():
            result.append((start + len(chunk) - len(chunk.lstrip()), chunk.strip()))
        if separator:
            start = separator.end()
    return result


def _is_heading(block: str) -> bool:
    """Markdown headings are structure, not body paragraphs."""
    return block.startswith("#")


def _units(text: str) -> tuple[list[str], list[list[str]]]:
    """Return fixed leading blocks and the movable units: chapters, or thirds of paragraphs."""
    items = [b for _, b in blocks(text)]
    chapters = [i for i, b in enumerate(items) if b.startswith("## ")]
    if chapters:
        bounds = [*chapters, len(items)]
        units = [items[a:b] for a, b in zip(bounds, bounds[1:], strict=False)]
        return items[: chapters[0]], units
    head = 1 if items and _is_heading(items[0]) else 0
    body = items[head:]
    if len(body) < 3:
        raise ValueError("Hacen falta al menos tres párrafos para barajar por tercios.")
    bounds = [round(i * len(body) / 3) for i in range(4)]
    return items[:head], [body[a:b] for a, b in zip(bounds, bounds[1:], strict=False)]


def shuffled(text: str, *, seed: int, story: str) -> tuple[str, list[int]]:
    """Reorder chapters (or paragraph thirds) reproducibly and never return the original order."""
    fixed, units = _units(text)
    if len(units) < 2:
        raise ValueError("Un solo capítulo no se puede barajar.")
    order = list(range(len(units)))
    random.Random(int(digest([seed, story, "shuffled"])[:16], 16)).shuffle(order)
    if order == sorted(order):
        order = order[1:] + order[:1]
    parts = [*fixed, *(block for i in order for block in units[i])]
    return "\n\n".join(parts) + "\n", order


def no_ending(text: str) -> tuple[str, int]:
    """Cut the final fifth of body paragraphs, returning a strict, shorter prefix of the text."""
    items = blocks(text)
    body = [i for i, (_, b) in enumerate(items) if not _is_heading(b)]
    if len(body) < 2:
        raise ValueError("Hacen falta al menos dos párrafos para quitar el desenlace.")
    removed = max(1, math.ceil(len(body) / 5))
    cut = body[-removed]
    while cut > 0 and _is_heading(items[cut - 1][1]):
        cut -= 1
    return text[: items[cut][0]].rstrip() + "\n", removed


def perturb_study(repository: StudyRepository, out: Path, *, seed: int = 0) -> list[Path]:
    """Write every perturbation of every frozen story with its provenance sidecar."""
    snapshot = repository.info()["snapshot"]
    if snapshot is None:
        raise ValueError("Primero abre la votación: asg-study open congela el conjunto.")
    written = []
    for story in repository.export()["stories"]:
        for kind in KINDS:
            if kind == "shuffled":
                text, order = shuffled(story["text"], seed=seed, story=story["id"])
                detail = {"seed": seed, "order": order}
            else:
                text, removed = no_ending(story["text"])
                detail = {"seed": None, "removed_paragraphs": removed}
            directory = out / f"{story['id']}-{kind}"
            atomic_write_text(directory / "story.md", text)
            atomic_write_json(
                directory / "perturbation.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "origin": {
                        "story": story["id"],
                        "text_hash": story["text_hash"],
                        "family": story["family"],
                    },
                    "study_sha256": snapshot["sha256"],
                    "type": kind,
                    "rule": RULES[kind],
                    **detail,
                    "text_hash": digest(text),
                },
            )
            written.append(directory)
    return written


def build_cases(repository: StudyRepository, out: Path) -> tuple[list[dict], list[str]]:
    """Pair study extractions with perturbed ones for `asg-judge --perturbations`."""
    stories = {s["id"]: s for s in repository.export()["stories"]}
    features = repository.path.parent / "features"
    cases, missing = [], []
    for sidecar in sorted(out.glob("*/perturbation.json")):
        directory = sidecar.parent
        meta = load_json_object(sidecar)
        origin = stories.get(meta.get("origin", {}).get("story"))
        text = (directory / "story.md").read_text(encoding="utf-8")
        original = load_json_object(features / f"{origin['id']}.json") if origin else {}
        perturbed = load_json_object(directory / "features" / "features.json")
        if (
            origin is None
            or meta.get("origin", {}).get("text_hash") != origin["text_hash"]
            or meta.get("text_hash") != digest(text)
            or not _compatible(original, origin["text_hash"])
            or not _compatible(perturbed, digest(text))
        ):
            missing.append(directory.name)
            continue
        cases.append(
            {
                "name": directory.name,
                "type": meta["type"],
                "original": original,
                "perturbed": perturbed,
            }
        )
    return cases, missing


def main(argv: list[str] | None = None) -> int:
    """Write the perturbed texts, or assemble the judge's perturbation cases from extractions."""
    parser = argparse.ArgumentParser(description="Perturbaciones por código del estudio congelado")
    parser.add_argument("db", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--casos", type=Path, help="Escribir el JSON de asg-judge --perturbations, sin textos"
    )
    args = parser.parse_args(argv)
    use_utf8_output()
    try:
        if not args.db.is_file():
            raise ValueError("No existe la base del estudio.")
        repository = StudyRepository(args.db)
        if args.casos:
            cases, missing = build_cases(repository, args.out)
            atomic_write_json(args.casos, cases)
            for name in missing:
                print(f"Sin extracción compatible: {name}", file=sys.stderr)
            print(json.dumps({"cases": len(cases), "missing": len(missing)}))
            return int(bool(missing))
        written = perturb_study(repository, args.out, seed=args.seed)
        print(json.dumps({"perturbations": len(written), "out": str(args.out)}, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
