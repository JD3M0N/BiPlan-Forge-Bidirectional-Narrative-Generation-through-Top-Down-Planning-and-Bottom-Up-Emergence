"""Operator commands for the pairwise study; no messaging or generation side effects."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from asg_core import atomic_write_json, use_utf8_output

from .study import StudyRepository


def parser() -> argparse.ArgumentParser:
    """Describe the lifecycle operations available to the researcher."""
    root = argparse.ArgumentParser(description="Administrar la evaluación humana por pares")
    root.add_argument("--db", type=Path, required=True, help="Base SQLite del estudio")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Fase, historias, lectores y votos")
    add = sub.add_parser("add", help="Inscribir runs completos (p. ej. líneas base)")
    add.add_argument("runs", type=Path, nargs="+")
    for name, text in (("exclude", "Sacar una historia del conjunto"), ("include", "Devolverla")):
        sub.add_parser(name, help=text).add_argument("story")
    author = sub.add_parser("author", help="Marcar al investigador por su ID de Telegram")
    author.add_argument("external_id")
    sub.add_parser("open", help="Congelar el conjunto y abrir la votación")
    sub.add_parser("close", help="Cerrar la votación")
    votes = sub.add_parser("import-votes", help="Importar votos transcritos de una hoja en papel")
    votes.add_argument("csv", type=Path)
    votes.add_argument(
        "--protocolo",
        type=Path,
        required=True,
        help="JSON con `protocolo` y `historias` (código de la hoja -> ID de historia)",
    )
    export = sub.add_parser("export", help="Exportar datos seudónimos a JSON")
    export.add_argument("output", type=Path)
    return root


def main(argv: list[str] | None = None) -> int:
    """Run one transactional study operation and print its result as JSON."""
    use_utf8_output()
    args = parser().parse_args(argv)
    try:
        result = _dispatch(StudyRepository(args.db), args)
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _dispatch(repository: StudyRepository, args) -> dict:
    """Execute one command and return only operator-relevant output."""
    if args.command == "add":
        return {"stories": [repository.add_story(run) for run in args.runs]}
    if args.command in {"exclude", "include"}:
        repository.exclude(args.story, args.command == "exclude")
    elif args.command == "author":
        return {"participant": repository.mark_author(args.external_id)}
    elif args.command == "open":
        return {"state": "evaluation", "sha256": repository.open()["sha256"]}
    elif args.command == "close":
        repository.close()
    elif args.command == "import-votes":
        return _import_votes(repository, args)
    elif args.command == "export":
        atomic_write_json(args.output, repository.export())
        return {"output": str(args.output)}
    return repository.status()


def _import_votes(repository: StudyRepository, args) -> dict:
    """Import a transcribed CSV and leave its protocol and SHA-256 next to the database."""
    raw = args.csv.read_bytes()
    protocol = json.loads(args.protocolo.read_text(encoding="utf-8"))
    codes, name = protocol.get("historias"), protocol.get("protocolo")
    if not isinstance(codes, dict) or not codes or not name:
        raise ValueError("El protocolo necesita `protocolo` e `historias`.")
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    result = repository.import_votes(rows, codes)
    stamp = {
        "protocolo": name,
        "csv": str(args.csv),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "historias": codes,
        **result,
    }
    atomic_write_json(repository.path.with_name("votos-importados.json"), stamp)
    return stamp
