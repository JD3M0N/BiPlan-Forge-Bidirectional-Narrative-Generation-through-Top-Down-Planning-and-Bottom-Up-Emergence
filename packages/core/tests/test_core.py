"""Tests for shared filesystem infrastructure."""

import asyncio
import json
from pathlib import Path

import pytest
from asg_core import (
    AudioGenerationError,
    atomic_write_json,
    atomic_write_text,
    create_story_audio,
    find_project_root,
    markdown_to_speech_text,
    slugify,
    stories_path,
)
from asg_core import audio as audio_module


def test_find_project_root_and_story_path(tmp_path):
    """Resolve the repository marker and build a story path below it."""
    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    nested = tmp_path / "apps" / "telegram"
    nested.mkdir(parents=True)

    assert find_project_root(nested) == tmp_path
    assert stories_path("Top-Down", root=tmp_path) == tmp_path / "Stories" / "Top-Down"


def test_slugify_uses_ascii_and_fallback():
    """Normalize accented names and provide a stable empty-value fallback."""
    assert slugify("La habitación final") == "la-habitacion-final"
    assert slugify("***", fallback="story") == "story"


def test_atomic_writers_replace_complete_files(tmp_path):
    """Persist text and JSON without leaving temporary files behind."""
    text_path = atomic_write_text(tmp_path / "note.txt", "hello")
    json_path = atomic_write_json(tmp_path / "data.json", {"value": "á"})

    assert text_path.read_text(encoding="utf-8") == "hello"
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"value": "á"}
    assert not list(tmp_path.glob("*.tmp"))


def test_markdown_is_cleaned_for_narration():
    source = (
        "# Título\n\n**Texto** con [enlace](https://example.com).\n\n"
        "~~~python\nprint('oculto')\n~~~\n\n- Final"
    )
    assert markdown_to_speech_text(source) == "Título\n\nTexto con enlace.\nFinal"


class FakeVoices:
    def find(self, **criteria):
        voices = [
            {
                "ShortName": "es-ES-GeneralNeural",
                "Language": "es",
                "VoiceTag": {"ContentCategories": ["General"]},
            },
            {
                "ShortName": "es-MX-NovelNeural",
                "Language": "es",
                "VoiceTag": {"ContentCategories": ["Novel"]},
            },
            {
                "ShortName": "en-US-NovelNeural",
                "Language": "en",
                "VoiceTag": {"ContentCategories": ["Novel"]},
            },
        ]
        return [voice for voice in voices if voice["Language"] == criteria["Language"]]


class FakeCommunicate:
    attempts = 0
    failures = 0

    def __init__(self, text, voice):
        self.text = text
        self.voice = voice

    async def save(self, destination):
        type(self).attempts += 1
        if type(self).attempts <= type(self).failures:
            raise OSError("temporary")
        Path(destination).write_bytes(f"{self.voice}:{self.text}".encode())


@pytest.fixture
def fake_tts(monkeypatch):
    FakeCommunicate.attempts = 0
    FakeCommunicate.failures = 0
    monkeypatch.setattr(audio_module.edge_tts, "Communicate", FakeCommunicate)
    return FakeVoices()


@pytest.mark.parametrize(
    ("text", "language", "voice"),
    [
        (
            "Esta es una historia extensa escrita completamente en español.",
            "es",
            "es-MX-NovelNeural",
        ),
        (
            "This is a sufficiently long story written entirely in English.",
            "en",
            "en-US-NovelNeural",
        ),
    ],
)
def test_story_audio_detects_language_and_selects_novel_voice(
    tmp_path, fake_tts, text, language, voice
):
    story = tmp_path / "story.md"
    story.write_text(f"# Relato\n\n{text}", encoding="utf-8")

    artifact = asyncio.run(create_story_audio(story, retry_delays=(), voice_manager=fake_tts))

    metadata = json.loads((tmp_path / "audio.json").read_text(encoding="utf-8"))
    assert artifact.path == tmp_path / "story.mp3"
    assert artifact.language == language
    assert artifact.voice == voice
    assert artifact.path.read_bytes()
    assert metadata["status"] == "completed"
    assert metadata["voice"] == voice
    assert not list(tmp_path.glob("*.tmp"))


def test_story_audio_retries_and_cleans_partial_files(tmp_path, fake_tts):
    story = tmp_path / "story.md"
    story.write_text("Una historia suficientemente larga para detectar español.", encoding="utf-8")
    FakeCommunicate.failures = 2

    artifact = asyncio.run(create_story_audio(story, retry_delays=(0, 0), voice_manager=fake_tts))

    assert artifact.path.is_file()
    assert FakeCommunicate.attempts == 3
    assert not list(tmp_path.glob("*.tmp"))


def test_story_audio_failure_is_controlled_and_recorded(tmp_path, fake_tts):
    story = tmp_path / "story.md"
    story.write_text("Una historia suficientemente larga para detectar español.", encoding="utf-8")
    FakeCommunicate.failures = 3

    with pytest.raises(AudioGenerationError):
        asyncio.run(create_story_audio(story, retry_delays=(0, 0)))

    metadata = json.loads((tmp_path / "audio.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["error"] == "OSError"
    assert not (tmp_path / "story.mp3").exists()
    assert not list(tmp_path.glob("*.tmp"))
