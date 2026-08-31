import argparse
import json

from asg_core import AudioGenerationError
from asg_escape_room import cli
from asg_escape_room.config import Settings


def test_seed_is_random_when_omitted(tmp_path, maps_dir, monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings(None, "test-model", tmp_path),
    )
    monkeypatch.setattr(cli.secrets, "randbits", lambda bits: 987654321)
    args = argparse.Namespace(
        map=maps_dir / "minimal_room.json",
        seed=None,
        agents=2,
        tick_limit=100,
        batch=False,
        no_llm=True,
    )
    output = cli.run_one(args)
    request = json.loads((output / "request.json").read_text(encoding="utf-8"))
    assert request["seed"] == 987654321
    evaluation = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation["schema_version"] == 1
    assert evaluation["evaluations"][0]["user"] is None
    assert (output / "story.mp3").read_bytes() == b"fake-mp3"
    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["audio_status"] == "completed"
    assert "audio" in metadata["completed_stages"]


def test_explicit_seed_is_preserved(tmp_path, maps_dir, monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings(None, "test-model", tmp_path),
    )
    args = argparse.Namespace(
        map=maps_dir / "minimal_room.json",
        seed=42,
        agents=2,
        tick_limit=100,
        batch=False,
        no_llm=True,
    )
    output = cli.run_one(args)
    request = json.loads((output / "request.json").read_text(encoding="utf-8"))
    assert request["seed"] == 42


def test_audio_failure_keeps_bottom_up_run_completed(tmp_path, maps_dir, monkeypatch) -> None:
    monkeypatch.setattr(cli, "load_settings", lambda: Settings(None, "test-model", tmp_path))

    def fail_audio(story_path):
        raise AudioGenerationError("tts unavailable")

    monkeypatch.setattr(cli, "create_story_audio_sync", fail_audio)
    args = argparse.Namespace(
        map=maps_dir / "minimal_room.json",
        seed=42,
        agents=2,
        tick_limit=100,
        batch=False,
        no_llm=True,
    )

    output = cli.run_one(args)

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["audio_status"] == "failed"
    assert metadata["audio_error"] == "AUDIO_GENERATION_FAILED"
    assert not (output / "story.mp3").exists()
