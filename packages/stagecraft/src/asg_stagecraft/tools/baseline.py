"""Single-prompt prose baseline using the configured provider without the story pipeline."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from asg_core import atomic_write_json, atomic_write_text, use_utf8_output

from ..runtime.config import load_settings
from ..runtime.provider import provider_from_settings
from ..version import GENERATOR_VERSION, PIPELINE_VERSION


def generate_baseline(provider, prompt: str, directory: Path, *, model: str) -> Path:
    """Persist one prompt and one prose response with comparable provenance and usage."""
    directory.mkdir(parents=True, exist_ok=False)
    created = datetime.now(UTC).isoformat()
    metadata = {
        "run_id": directory.name,
        "status": "running",
        "story_format": "baseline",
        "model": model,
        "pipeline_version": PIPELINE_VERSION,
        "created_at": created,
        "updated_at": created,
        "warnings": [],
    }
    atomic_write_json(directory / "request.json", {"original_prompt": prompt})
    atomic_write_json(directory / "generation_options.json", {"story_format": "baseline"})
    atomic_write_json(
        directory / "generator_version.json",
        {"generator_version": GENERATOR_VERSION, "pipeline_version": PIPELINE_VERSION},
    )
    atomic_write_json(directory / "metadata.json", metadata)
    before = len(getattr(provider, "usage_records", []))
    try:
        text = provider.generate_text(
            system_instruction="Escribe una historia completa en prosa, en español. "
            "Devuelve solo el relato, sin comentarios sobre cómo lo generaste.",
            prompt=prompt,
            profile="prose",
        )
        if not text.strip():
            raise ValueError("La línea base devolvió un texto vacío.")
        atomic_write_text(directory / "story.md", text)
        metadata["status"] = "completed"
    except Exception:
        metadata["status"] = "failed"
        raise
    finally:
        metadata["updated_at"] = datetime.now(UTC).isoformat()
        atomic_write_json(directory / "metadata.json", metadata)
        records = [
            r.model_dump(mode="json") for r in getattr(provider, "usage_records", [])[before:]
        ]
        atomic_write_json(
            directory / "llm_usage.json",
            {
                "records": records,
                "calls": len({r["call_id"] for r in records}),
                "total_tokens": sum(r["total_tokens"] for r in records),
                "failed_attempts": sum(r["status"] == "failed" for r in records),
            },
        )
    return directory


def main(argv: list[str] | None = None) -> int:
    """Create a baseline only when explicitly invoked by the operator."""
    parser = argparse.ArgumentParser(description="Generación directa de línea base (consume cuota)")
    parser.add_argument("prompt")
    parser.add_argument("--output", type=Path, required=True, help="Carpeta nueva del run")
    args = parser.parse_args(argv)
    use_utf8_output()
    settings = load_settings()
    directory = generate_baseline(
        provider_from_settings(settings), args.prompt, args.output, model=settings.model
    )
    print(directory)
    return 0
