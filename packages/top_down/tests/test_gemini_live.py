import hashlib
import json
import os
from pathlib import Path

import pytest
from asg_top_down import StoryGenerator
from asg_top_down.config import load_settings
from asg_top_down.provider import GeminiProvider

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROMPT_CATALOG = REPOSITORY_ROOT / "docs" / "prompts_top_down.md"
PROMPT_START = "<!-- PROMPT_01_START -->"
PROMPT_END = "<!-- PROMPT_01_END -->"


def _canonical_prompt() -> str:
    """Load the canonical Gemini prompt from its documented source of truth."""
    catalog = PROMPT_CATALOG.read_text(encoding="utf-8")
    if catalog.count(PROMPT_START) != 1 or catalog.count(PROMPT_END) != 1:
        raise ValueError("the prompt catalog must contain one canonical prompt marker pair")
    prompt = catalog.split(PROMPT_START, 1)[1].split(PROMPT_END, 1)[0].strip()
    if not prompt:
        raise ValueError("the canonical Gemini prompt cannot be empty")
    return prompt


CANONICAL_PROMPT = _canonical_prompt()

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GEMINI_LIVE") != "1",
    reason="set RUN_GEMINI_LIVE=1 to spend Gemini quota",
)


def test_real_gemini_smoke_run() -> None:
    settings = load_settings()
    provider = GeminiProvider(
        settings.api_key,
        settings.model,
        rpm_limit=settings.rpm_limit,
        rpm_reserve=settings.rpm_reserve,
        tpm_limit=settings.tpm_limit,
        max_retries=settings.max_retries,
        max_retry_delay=settings.max_retry_delay,
        request_timeout_ms=settings.request_timeout_ms,
    )
    run = StoryGenerator(provider, settings.output_root).run(CANONICAL_PROMPT)
    assert run.story_path.is_file()
    assert len(run.story_path.read_text(encoding="utf-8").split()) >= 300

    request = json.loads((run.run_dir / "request.json").read_text(encoding="utf-8"))
    metadata = json.loads((run.run_dir / "metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((run.run_dir / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert request["original_prompt"] == CANONICAL_PROMPT
    assert request["target_words"] == 2500
    assert metadata["status"] == "completed"
    assert metadata["model"] == settings.model
    assert (run.run_dir / "evaluation.json").is_file()

    required_artifacts = {
        "generator_version.json",
        "request.json",
        "world.json",
        "characters.json",
        "story_plan.json",
        "draft.md",
        "length_audit.json",
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
