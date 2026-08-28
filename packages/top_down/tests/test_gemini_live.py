import os

import pytest
from asg_top_down import StoryGenerator
from asg_top_down.config import load_settings
from asg_top_down.provider import GeminiProvider

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
    run = StoryGenerator(provider, settings.output_root).run(
        "Escribe un relato esperanzador de 500 palabras en un capítulo sobre una "
        "reparadora de radios que capta una señal imposible."
    )
    assert run.story_path.is_file()
    assert len(run.story_path.read_text(encoding="utf-8").split()) >= 300
