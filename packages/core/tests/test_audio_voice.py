"""0.6.0: the story audio can be read with a voice the caller picks, and sampled first."""

import asyncio
import json
from pathlib import Path

import pytest
from asg_core import (
    NARRATION_VOICE_NAMES,
    NARRATION_VOICES,
    AudioGenerationError,
    create_story_audio,
    create_voice_sample_sync,
)
from asg_core import audio as audio_module


class RecordingCommunicate:
    """Stand in for edge-tts, remembering which voice read what."""

    voices: list[str] = []
    fail = False

    def __init__(self, text, voice):
        self.text = text
        self.voice = voice

    async def save(self, destination):
        type(self).voices.append(self.voice)
        if type(self).fail:
            raise OSError("no network")
        Path(destination).write_bytes(f"{self.voice}:{self.text}".encode())


@pytest.fixture
def recorder(monkeypatch):
    RecordingCommunicate.voices = []
    RecordingCommunicate.fail = False
    monkeypatch.setattr(audio_module.edge_tts, "Communicate", RecordingCommunicate)
    return RecordingCommunicate


def spanish_story(tmp_path):
    story = tmp_path / "story.md"
    story.write_text("# Relato\n\nUna historia escrita en español de principio a fin.", "utf-8")
    return story


def test_the_catalog_lists_every_spanish_voice_once_with_spain_first() -> None:
    assert len(NARRATION_VOICES) == 45
    assert len(NARRATION_VOICE_NAMES) == 45
    assert NARRATION_VOICES[0].name == "es-ES-AlvaroNeural"
    assert all(voice.name.startswith("es-") for voice in NARRATION_VOICES)
    assert {voice.gender for voice in NARRATION_VOICES} == {"mujer", "hombre"}
    assert all(voice.display_name and voice.country for voice in NARRATION_VOICES)


def test_a_chosen_voice_reads_the_story_instead_of_the_automatic_one(tmp_path, recorder) -> None:
    story = spanish_story(tmp_path)
    artifact = asyncio.run(create_story_audio(story, retry_delays=(), voice="es-MX-DaliaNeural"))
    assert artifact.voice == "es-MX-DaliaNeural"
    assert recorder.voices == ["es-MX-DaliaNeural"]
    metadata = json.loads((tmp_path / "audio.json").read_text(encoding="utf-8"))
    assert metadata["voice"] == "es-MX-DaliaNeural"


def test_a_finished_audio_is_reused_only_with_the_same_voice(tmp_path, recorder) -> None:
    story = spanish_story(tmp_path)
    asyncio.run(create_story_audio(story, retry_delays=()))
    assert recorder.voices == ["es-ES-AlvaroNeural"]
    # No voice asked for: whatever was read before is kept.
    asyncio.run(create_story_audio(story, retry_delays=()))
    assert recorder.voices == ["es-ES-AlvaroNeural"]
    # Another voice asked for: read again.
    asyncio.run(create_story_audio(story, retry_delays=(), voice="es-CU-BelkysNeural"))
    assert recorder.voices == ["es-ES-AlvaroNeural", "es-CU-BelkysNeural"]
    asyncio.run(create_story_audio(story, retry_delays=(), voice="es-CU-BelkysNeural"))
    assert recorder.voices == ["es-ES-AlvaroNeural", "es-CU-BelkysNeural"]


def test_a_voice_sample_is_written_or_fails_cleanly(tmp_path, recorder) -> None:
    sample = create_voice_sample_sync("es-AR-TomasNeural", tmp_path / "muestra.mp3")
    assert sample.read_bytes().startswith(b"es-AR-TomasNeural:")
    recorder.fail = True
    with pytest.raises(AudioGenerationError):
        create_voice_sample_sync("es-AR-TomasNeural", tmp_path / "otra.mp3", retry_delays=())
    assert not (tmp_path / "otra.mp3").exists()
