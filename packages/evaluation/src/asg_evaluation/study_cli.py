"""Local administration of research studies; no messaging or generation side effects."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from asg_core import atomic_write_json, use_utf8_output

from .study import StudyRepository
from .transfer import export_bundle, import_bundle


def parser() -> argparse.ArgumentParser:
    """Describe explicit lifecycle operations and their operator-supplied inputs."""
    root = argparse.ArgumentParser(description="Administrar evaluación humana por pares")
    root.add_argument("--db", type=Path)
    sub = root.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("id")
    create.add_argument("--version", required=True)
    create.add_argument("--seed", type=int, default=42)
    create.add_argument("--mode", choices=("fixed", "rolling"), default="fixed")
    participant = sub.add_parser("participant")
    participant.add_argument("external_id", help="ID de Telegram; no se publica en los informes")
    participant.add_argument("--profile", required=True)
    participant.add_argument("--author", action="store_true")
    enroll = sub.add_parser("add")
    enroll.add_argument("run", type=Path)
    enroll.add_argument("--owner", help="Seudónimo p... de quien creó el relato")
    enroll.add_argument("--curated", action="store_true")
    enroll.add_argument("--family", help="Familia de premisa; por defecto huella del prompt")
    for name in ("collect", "freeze", "start", "close", "status"):
        sub.add_parser(name)
    export = sub.add_parser("export")
    export.add_argument("output", type=Path)
    bundle = sub.add_parser("export-bundle")
    bundle.add_argument("output", type=Path)
    transfer = sub.add_parser("import-bundle")
    transfer.add_argument("source", type=Path)
    transfer.add_argument("output", type=Path)
    seeds = sub.add_parser("seed-bundle")
    seeds.add_argument("source", type=Path)
    seeds.add_argument("output", type=Path, help="Carpeta nueva para las historias importadas")
    return root


def main(argv: list[str] | None = None) -> int:
    """Run one transactional study administration operation."""
    use_utf8_output()
    args = parser().parse_args(argv)
    try:
        if args.command == "import-bundle":
            print(json.dumps(import_bundle(args.source, args.output), ensure_ascii=False))
            return 0
        if args.db is None:
            raise ValueError("Indica --db para operar sobre un estudio.")
        if args.command != "create" and not args.db.is_file():
            raise ValueError("No existe la base del estudio.")
        repository = StudyRepository(args.db)
        result = _dispatch(repository, args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _dispatch(repository: StudyRepository, args) -> dict:
    """Execute one command and return only operator-relevant output."""
    if args.command == "create":
        repository.create(args.id, required_version=args.version, seed=args.seed, mode=args.mode)
    elif args.command == "participant":
        reader = repository.participant(
            args.external_id, profile=args.profile, is_author=args.author
        )
        return {"participant": reader["id"]}
    elif args.command == "add":
        return {
            "story": repository.add_story(
                args.run, owner=args.owner, curated=args.curated, family=args.family
            )
        }
    elif args.command == "freeze":
        snapshot = repository.freeze()
        return {"state": "frozen", "sha256": snapshot["sha256"]}
    elif args.command in {"collect", "start", "close"}:
        repository.transition(
            {"collect": "collection", "start": "evaluation", "close": "closed"}[args.command]
        )
    elif args.command == "seed-bundle":
        import_bundle(args.source, args.output)
        for directory in sorted((args.output / "stories").iterdir()):
            repository.add_story(directory, curated=True)
    elif args.command == "export-bundle":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(export_bundle(repository))
        return {"output": str(args.output)}
    elif args.command == "export":
        atomic_write_json(args.output, repository.export())
        return {"output": str(args.output)}
    data = repository.export()
    return {
        "study": data["study"]["id"],
        "state": data["study"]["state"],
        "stories": len(data["stories"]),
        "participants": len(data["participants"]),
        "coverage": data["coverage"],
    }
