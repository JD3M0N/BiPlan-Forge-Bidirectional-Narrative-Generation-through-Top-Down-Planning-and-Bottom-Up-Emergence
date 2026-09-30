import hashlib
import json
import os
from pathlib import Path

import pytest
from asg_stagecraft import StoryGenerator
from asg_stagecraft.agents import AnalystAgent
from asg_stagecraft.runtime.config import load_settings
from asg_stagecraft.runtime.provider import provider_from_settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_PROMPT = (
    "Escribe en español un relato de fantasía épica con perfil narrativo Expansiva. Sir "
    "Aldren, un caballero veterano atormentado por el fracaso de una misión anterior, "
    "debe entrar en una fortaleza levantada sobre un volcán para rescatar a la princesa "
    "Elara de un dragón ancestral. Elara no debe ser una víctima pasiva: debe investigar "
    "su cautiverio, tomar decisiones arriesgadas y contribuir de forma decisiva a su "
    "propia liberación. El dragón debe tener una motivación comprensible relacionada con "
    "una antigua promesa rota por el reino, y no ser simplemente un monstruo malvado. "
    "Desarrolla una cadena causal clara desde la llegada del caballero hasta el "
    "enfrentamiento final; prepara con antelación cualquier objeto, conocimiento o "
    "habilidad que resulte decisivo. Mantén la continuidad de lugares, heridas, "
    "información y relaciones. Usa un tono aventurero y emotivo, incluye un dilema moral "
    "que obligue a Aldren a elegir entre obedecer al rey y hacer lo correcto, y termina "
    "con un desenlace cerrado y esperanzador. Evita el deus ex machina, las profecías que "
    "resuelven el conflicto por sí solas y las explicaciones sobre el proceso de "
    "escritura."
)


def _canonical_prompt() -> str:
    """Return the canonical Gemini regression prompt."""
    return CANONICAL_PROMPT


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GEMINI_LIVE") != "1",
    reason="set RUN_GEMINI_LIVE=1 to spend Gemini quota",
)


def test_real_gemini_smoke_run() -> None:
    canonical_prompt = _canonical_prompt()
    settings = load_settings()
    provider = provider_from_settings(settings)
    run = StoryGenerator(provider, settings.output_root).generate(canonical_prompt)
    assert run.story_path.is_file()
    assert run.story_path.read_text(encoding="utf-8").strip()

    request = json.loads((run.run_dir / "request.json").read_text(encoding="utf-8"))
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((run.run_dir / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert request["original_prompt"] == canonical_prompt
    assert request["narrative_profile"] in {"essential", "developed", "expansive"}
    assert metadata["status"] == "completed"
    assert metadata["model"] == settings.model
    assert (run.run_dir / "evaluation.json").is_file()

    required_artifacts = {
        "generator_version.json",
        "request.json",
        "world.json",
        "characters.json",
        "plan_review.json",
        "story_plan.json",
        "draft_presentation.json",
        "draft.md",
        "review.json",
        "story_metrics.json",
        "llm_calls.jsonl",
        "llm_usage.json",
        "metadata.json",
        "story.md",
    }
    assert required_artifacts <= set(manifest["artifacts"])
    for relative_path, recorded in manifest["artifacts"].items():
        artifact = run.run_dir / relative_path
        content = artifact.read_bytes()
        assert len(content) == recorded["bytes"]
        assert hashlib.sha256(content).hexdigest() == recorded["sha256"]


def test_real_analyst_enriches_a_sparse_request() -> None:
    settings = load_settings()
    provider = provider_from_settings(settings)
    prompt = "Crea una historia de un caballero que salva a una princesa de un dragón"
    request = AnalystAgent(provider).run(prompt)
    assert request.original_prompt == prompt
    assert request.language == "Spanish"
    assert request.processed_prompt
    assert len(request.processed_prompt.split()) > len(prompt.split())
    assert request.creative_directions
