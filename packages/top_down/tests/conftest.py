import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).parents[1] / "src"
sys.path.insert(0, str(SOURCE))


@pytest.fixture(autouse=True)
def fake_story_audio(monkeypatch):
    """Avoid network TTS while preserving the generated artifact contract."""
    from asg_top_down import pipeline as pipeline_module

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
