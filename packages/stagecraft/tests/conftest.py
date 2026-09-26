import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def fake_story_audio(monkeypatch):
    """Avoid network TTS while preserving the generated artifact contract."""
    from asg_stagecraft import pipeline as pipeline_module

    def create(story_path):
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

    monkeypatch.setattr(pipeline_module, "create_story_audio_sync", create)
