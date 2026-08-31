from pathlib import Path
from types import SimpleNamespace

import pytest
from asg_escape_room import load_room


@pytest.fixture
def maps_dir() -> Path:
    return Path(__file__).parents[3] / "packages" / "escape_room" / "maps"


@pytest.fixture
def room(maps_dir):
    return load_room(maps_dir / "minimal_room.json")


@pytest.fixture(autouse=True)
def fake_story_audio(monkeypatch):
    """Avoid external TTS calls from console generation tests."""
    from asg_escape_room import cli

    def create(story_path):
        audio_path = Path(story_path).with_suffix(".mp3")
        audio_path.write_bytes(b"fake-mp3")
        (audio_path.parent / "audio.json").write_text(
            '{"status":"completed","language":"es","voice":"fake"}',
            encoding="utf-8",
        )
        return SimpleNamespace(path=audio_path, language="es", voice="fake")

    monkeypatch.setattr(cli, "create_story_audio_sync", create)
