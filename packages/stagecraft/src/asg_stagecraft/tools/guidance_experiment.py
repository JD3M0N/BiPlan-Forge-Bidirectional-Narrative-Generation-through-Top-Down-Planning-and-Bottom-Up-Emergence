"""Prepare a frozen, balanced guidance comparison without constructing an LLM provider."""

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from asg_core import atomic_write_json, use_utf8_output

from ..options import GenerationOptions
from ..planning.catalog import CATALOG_HASH, CATALOG_VERSION
from ..planning.profiles import NarrativeProfile
from ..schemas import StoryRequest
from ..version import GENERATOR_VERSION

ARMS = (
    ("no_guidance", False, "hybrid_v1"),
    ("hybrid_v1", True, "hybrid_v1"),
    ("compositional_v2", True, "compositional_v2"),
)


def experiment_manifest(
    requests: list[StoryRequest],
    *,
    model: str,
    full: bool = False,
    options: GenerationOptions | None = None,
    pilot_usage: list[dict] | None = None,
) -> dict:
    """Freeze nine pilot or thirty-six full-study jobs with exactly paired request snapshots."""
    expected = 2 if full else 1
    counts = Counter(request.narrative_profile for request in requests)
    if counts != {profile: expected for profile in NarrativeProfile}:
        raise ValueError(f"Se requieren {expected} premisas por cada perfil narrativo.")
    signatures = {json.dumps(request.agent_spec(), sort_keys=True) for request in requests}
    if len(signatures) != len(requests):
        raise ValueError("Las premisas deben ser distintas.")
    base = (options or GenerationOptions()).with_changes(story_format="narrative", audio=False)
    jobs = []
    for request in requests:
        snapshot = request.model_dump(mode="json")
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        for repetition in range(1, (2 if full else 1) + 1):
            for arm, enabled, strategy in ARMS:
                job_options = base.with_changes(
                    narrative_profile=request.narrative_profile,
                    narrative_guidance=enabled,
                    guidance_strategy=strategy,
                )
                jobs.append(
                    {
                        "job_id": f"{digest[:12]}-{repetition}-{arm}",
                        "request_hash": digest,
                        "request": snapshot,
                        "arm": arm,
                        "repetition": repetition,
                        "model": model,
                        "options": job_options.model_dump(mode="json"),
                    }
                )
    random.Random(42).shuffle(jobs)
    return {
        "status": "planned_not_generated",
        "generator_version": GENERATOR_VERSION,
        "catalog_version": CATALOG_VERSION,
        "catalog_hash": CATALOG_HASH,
        "phase": "full" if full else "pilot",
        "randomization_seed": 42,
        "jobs": jobs,
        "budget_estimate": _budget(len(jobs), pilot_usage),
        "human_criteria": ["creatividad", "desarrollo de personajes", "interés de la trama"],
        "reuse_policy": "Reutilizar piloto solo con los mismos contratos, prompts y opciones.",
    }


def _budget(count: int, pilot_usage: list[dict] | None) -> dict:
    """Estimate usage transparently; a forecast never authorizes generation or promises a cap."""
    if pilot_usage:
        if any(
            not isinstance(row.get(key), (int, float)) or row[key] < 0
            for row in pilot_usage
            for key in ("calls", "total_tokens")
        ):
            raise ValueError("El consumo piloto necesita calls y total_tokens no negativos.")
        calls = sum(row["calls"] for row in pilot_usage) / len(pilot_usage)
        tokens = sum(row["total_tokens"] for row in pilot_usage) / len(pilot_usage)
        basis = "media de los artefactos piloto suministrados"
    else:
        calls, tokens = 16, 84000
        basis = "referencia histórica del roadmap; no medida para v2"
    return {
        "basis": basis,
        "runs": count,
        "calls": round(calls * count),
        "total_tokens": round(tokens * count),
        "authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    """Write an experiment manifest from reviewed requests without loading keys or using quota."""
    use_utf8_output()
    parser = argparse.ArgumentParser(description="Prepara la comparación de guías sin generar")
    parser.add_argument("requests", nargs="+", type=Path, help="request.json revisados")
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--full", action="store_true", help="36 historias; por defecto, piloto de 9"
    )
    parser.add_argument("--options", type=Path)
    parser.add_argument("--pilot-usage", nargs="*", type=Path, default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError(
                "La salida ya existe; elige otro archivo para conservar el manifiesto."
            )
        requests = [
            StoryRequest.model_validate_json(path.read_text(encoding="utf-8"))
            for path in args.requests
        ]
        options = (
            GenerationOptions.model_validate_json(args.options.read_text(encoding="utf-8"))
            if args.options
            else None
        )
        usage = [json.loads(path.read_text(encoding="utf-8")) for path in args.pilot_usage]
        manifest = experiment_manifest(
            requests, model=args.model, full=args.full, options=options, pilot_usage=usage
        )
        atomic_write_json(args.output, manifest)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(f"Plan guardado: {args.output}. No se ha generado ninguna historia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
