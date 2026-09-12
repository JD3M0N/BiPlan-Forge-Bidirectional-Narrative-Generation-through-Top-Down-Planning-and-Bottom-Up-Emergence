import json
from types import SimpleNamespace
from unittest.mock import create_autospec

from asg_console import evaluation as evaluation_module
from asg_console import top_down as top_down_module
from asg_console.app import ConsoleApp, TopDownMenu
from asg_top_down import StoryGenerator
from asg_top_down import provider as top_down_provider_module


class MenuSpy:
    def __init__(self) -> None:
        self.calls = 0

    def run(self) -> None:
        self.calls += 1


def input_sequence(values):
    iterator = iter(values)
    return lambda prompt="": next(iterator)


def test_main_menu_navigates_both_models_and_rejects_bad_input() -> None:
    top = MenuSpy()
    bottom = MenuSpy()
    messages = []
    application = ConsoleApp(
        input_fn=input_sequence(["1", "2", "x", "0"]),
        output=messages.append,
        top_down=top,
        bottom_up=bottom,
    )
    assert application.run() == 0
    assert top.calls == 1
    assert bottom.calls == 1
    assert "Opción inválida." in messages


def test_top_down_passes_prompt_to_orchestrator(tmp_path, monkeypatch) -> None:
    captured = {}

    class Provider:
        def __init__(self, api_key, model, **kwargs):
            self.model_name = model
            captured["provider_options"] = kwargs

    def build_generator(provider, output_root, **kwargs):
        captured["generator_options"] = kwargs
        instance = create_autospec(StoryGenerator, spec_set=True, instance=True)

        def generate(request, on_progress=None, on_run_created=None, on_event=None):
            captured["prompt"] = request
            return SimpleNamespace(run_dir=tmp_path)

        instance.generate.side_effect = generate
        return instance

    Orchestrator = create_autospec(StoryGenerator, spec_set=True)
    Orchestrator.side_effect = build_generator

    settings = type(
        "Settings",
        (),
        {
            "api_key": "test",
            "model": "fake",
            "output_root": tmp_path,
            "rpm_limit": 10,
            "rpm_reserve": 2,
            "tpm_limit": 3000,
            "max_retries": 4,
            "max_retry_delay": 30,
            "request_timeout_ms": 45000,
            "narrative_guidance": True,
        },
    )()
    monkeypatch.setattr(top_down_module, "load_top_down_settings", lambda: settings)
    monkeypatch.setattr(top_down_provider_module, "GeminiProvider", Provider)
    monkeypatch.setattr(top_down_module, "StoryGenerator", Orchestrator)
    menu = TopDownMenu(
        input_fn=input_sequence(["1", "Una historia", "0"]),
        output=lambda message: None,
    )
    menu.run()
    assert captured["prompt"] == "Una historia"
    assert captured["provider_options"]["max_retries"] == 4
    assert captured["generator_options"] == {"narrative_guidance": True}


def test_console_evaluates_story_and_retries_invalid_values(tmp_path, monkeypatch) -> None:
    story = tmp_path / "Stories" / "Top-Down" / "story-one"
    story.mkdir(parents=True)
    (story / "story.md").write_text("# Historia", encoding="utf-8")
    monkeypatch.setattr(evaluation_module, "find_project_root", lambda: tmp_path)
    messages = []
    application = ConsoleApp(
        input_fn=input_sequence(
            [
                "x",
                "1",
                "",
                "Ana",
                "0",
                "8",
                "9",
                "7",
                "10",
                "8",
                "9",
            ]
        ),
        output=messages.append,
        top_down=MenuSpy(),
        bottom_up=MenuSpy(),
    )
    application._evaluate_story()
    document = json.loads((story / "evaluation.json").read_text(encoding="utf-8"))
    assert document["evaluations"][0] == {
        "user": "Ana",
        "coherence": 8,
        "pacing": 9,
        "creativity": 7,
        "engagement": 10,
        "relevance": 8,
        "satisfaction": 9,
    }
    assert "Selección inválida." in messages
    assert "El usuario no puede estar vacío." in messages
    assert "Introduce un entero entre 1 y 10." in messages
