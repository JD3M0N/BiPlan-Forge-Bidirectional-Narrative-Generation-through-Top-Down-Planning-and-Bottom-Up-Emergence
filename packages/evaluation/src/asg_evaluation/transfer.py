"""Portable verified research bundles independent of the server's filesystem."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from asg_core import atomic_write_json, atomic_write_text

from .catalog import digest
from .restore import restore_analysis_database


def json_bytes(value) -> bytes:
    """Encode a portable UTF-8 JSON document."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def portable_provenance(value):
    """Remove administrative identifiers and host paths from nested run artifacts."""
    if isinstance(value, dict):
        return {
            key: portable_provenance(item)
            for key, item in value.items()
            if not any(
                term in key.lower()
                for term in (
                    "path",
                    "directory",
                    "run_dir",
                    "output_root",
                    "telegram",
                    "chat_id",
                    "user_id",
                    "username",
                    "external_id",
                    "api_key",
                    "access_token",
                    "bot_token",
                    "password",
                )
            )
        }
    if isinstance(value, list):
        return [portable_provenance(item) for item in value]
    if isinstance(value, str) and (re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith("/")):
        return "[ruta local omitida]"
    return value


def export_bundle(repository) -> bytes:
    """Create one consistent data bundle with byte hashes for every included file."""
    data = repository.export()
    files = {"study.json": json_bytes(data)}
    for story in data["stories"]:
        files[f"stories/{story['id']}/story.md"] = story["text"].encode("utf-8")
    manifest = {
        "schema_version": 1,
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json_bytes(manifest))
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def split_bundle(payload: bytes, limit: int = 45_000_000) -> list[tuple[str, bytes]]:
    """Split large ZIPs into numbered binary parts that can be rejoined without loss."""
    if len(payload) <= limit:
        return [("estudio.zip", payload)]
    return [
        (f"estudio.zip.part{index // limit + 1:04d}", payload[index : index + limit])
        for index in range(0, len(payload), limit)
    ]


def import_bundle(source: Path, destination: Path) -> dict:
    """Verify the complete archive before creating a new portable analysis directory."""
    payload = _read_bundle(source)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schema_version") != 1:
            raise ValueError("Versión de exportación desconocida.")
        expected = manifest["files"]
        if set(archive.namelist()) != {*expected, "manifest.json"}:
            raise ValueError("El ZIP contiene archivos no declarados.")
        files = {name: archive.read(name) for name in expected}
        for name, content in files.items():
            if hashlib.sha256(content).hexdigest() != expected[name]:
                raise ValueError("La huella de un archivo no coincide.")
        data = json.loads(files["study.json"])
        for story in data["stories"]:
            if not re.fullmatch(r"s[a-zA-Z0-9_-]+", story["id"]):
                raise ValueError("Identificador de historia inválido.")
            if digest(story["text"]) != story["text_hash"]:
                raise ValueError("El texto de una historia fue modificado.")
            if files[f"stories/{story['id']}/story.md"].decode("utf-8") != story["text"]:
                raise ValueError("El texto del ZIP no coincide con el estudio.")
    destination.mkdir(parents=True, exist_ok=False)
    atomic_write_json(destination / "study.json", data)
    atomic_write_json(destination / "manifest.json", manifest)
    for story in data["stories"]:
        run = destination / "stories" / story["id"]
        run.mkdir(parents=True)
        atomic_write_text(run / "story.md", story["text"])
        for key, name in (
            ("metadata", "metadata"),
            ("options", "generation_options"),
            ("version", "generator_version"),
            ("request", "request"),
            ("source", "source_run"),
        ):
            atomic_write_json(run / f"{name}.json", story["provenance"].get(key, {}))
    restore_analysis_database(data, destination)
    return {"output": str(destination), "stories": len(data["stories"])}


def _read_bundle(source: Path) -> bytes:
    """Join contiguous numbered parts or read a standalone ZIP."""
    if not source.name.endswith(".part0001"):
        return source.read_bytes()
    prefix = source.name[:-4]
    parts = sorted(source.parent.glob(prefix + "[0-9][0-9][0-9][0-9]"))
    if [p.name for p in parts] != [prefix + f"{i:04d}" for i in range(1, len(parts) + 1)]:
        raise ValueError("Falta una parte del ZIP.")
    return b"".join(part.read_bytes() for part in parts)
