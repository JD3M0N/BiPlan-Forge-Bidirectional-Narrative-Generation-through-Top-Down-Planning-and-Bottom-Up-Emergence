import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def _create(story_path):
    audio_path = Path(story_path).with_suffix(".mp3")
    audio_path.write_bytes(b"fake-mp3")
    (audio_path.parent / "audio.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "language": "es",
                "voice": "es-MX-FakeNeural",
            }
        ),
        encoding="utf-8",
    )
    return SimpleNamespace(path=audio_path, language="es", voice="es-MX-FakeNeural")


@pytest.fixture(autouse=True, scope="session")
def fake_story_audio():
    """Avoid network TTS while preserving the generated artifact contract.

    Session-scoped so the session-scoped pipeline-run fixtures in
    ``pipeline_fakes.py`` never reach the real TTS. Individual tests still
    override it with their own ``monkeypatch.setattr`` when they need to.
    """
    from asg_stagecraft import pipeline as pipeline_module

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pipeline_module, "create_story_audio_sync", _create)
        yield
