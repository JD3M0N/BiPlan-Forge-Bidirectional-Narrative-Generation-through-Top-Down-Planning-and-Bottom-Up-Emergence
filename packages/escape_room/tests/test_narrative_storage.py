import json

from asg_escape_room import run_simulation
from asg_escape_room.narrative import generate_story
from asg_escape_room.storage import RunRepository


class FakeProvider:
    model_name = "fake-model"

    def generate_text(self, *, system_instruction: str, prompt: str) -> str:
        assert "tercera persona" in system_instruction
        assert "causal_timeline" in prompt
        return "# Relato generado"


class BrokenProvider:
    model_name = "broken"

    def generate_text(self, *, system_instruction: str, prompt: str) -> str:
        raise RuntimeError("sin conexión")


def test_narrative_provider_is_injectable(room) -> None:
    result, model = run_simulation(room, tick_limit=100)
    story, source, error = generate_story(result, model.event_log, FakeProvider())
    assert story == "# Relato generado"
    assert source == "gemini"
    assert error is None


def test_narrative_falls_back_on_provider_error(room) -> None:
    result, model = run_simulation(room, tick_limit=100)
    story, source, error = generate_story(result, model.event_log, BrokenProvider())
    assert story.startswith("# La habitación")
    assert source == "fallback"
    assert error == "sin conexión"


def test_repository_never_persists_api_key(tmp_path) -> None:
    repository = RunRepository(tmp_path, "Prueba", "fake")
    metadata = json.loads((repository.run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert "api_key" not in metadata
