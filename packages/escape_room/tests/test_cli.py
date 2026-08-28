import argparse
import json

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
