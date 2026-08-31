import argparse
import json

from asg_console import bottom_up as bottom_up_module
from asg_console import evaluation as evaluation_module
from asg_console import top_down as top_down_module
from asg_console.app import BottomUpMenu, ConsoleApp, TopDownMenu
from asg_console.visualizer import VisualOutcome
from asg_escape_room import run_simulation
from asg_escape_room.config import Settings as BottomSettings


class MenuSpy:
    def __init__(self) -> None:
        self.calls = 0

    def run(self) -> None:
        self.calls += 1


def input_sequence(values):
    iterator = iter(values)
    return lambda prompt="": next(iterator)


def test_main_menu_navigates_both_models() -> None:
    top = MenuSpy()
    bottom = MenuSpy()
    messages = []
    application = ConsoleApp(
        input_fn=input_sequence(["1", "2", "0"]),
        output=messages.append,
        top_down=top,
        bottom_up=bottom,
    )
    assert application.run() == 0
    assert top.calls == 1
    assert bottom.calls == 1


def test_invalid_main_option_is_reported() -> None:
    messages = []
    application = ConsoleApp(
        input_fn=input_sequence(["x", "0"]),
        output=messages.append,
        top_down=MenuSpy(),
        bottom_up=MenuSpy(),
    )
    assert application.run() == 0
    assert "Opción inválida." in messages


def test_top_down_passes_prompt_to_orchestrator(tmp_path, monkeypatch) -> None:
    captured = {}

    class Provider:
        def __init__(self, api_key, model, **kwargs):
            self.model_name = model
            captured["provider_options"] = kwargs

    class Orchestrator:
        def __init__(self, provider, output_root, **kwargs):
            captured["generator_options"] = kwargs

        def run(self, prompt):
            captured["prompt"] = prompt
            return tmp_path

    settings = type(
        "Settings",
        (),
        {
            "api_key": "test",
            "model": "fake",
            "output_root": tmp_path,
            "default_target_words": 1500,
            "rpm_limit": 10,
            "rpm_reserve": 2,
            "tpm_limit": 3000,
            "max_retries": 4,
            "max_retry_delay": 30,
            "request_timeout_ms": 45000,
        },
    )()
    monkeypatch.setattr(top_down_module, "load_top_down_settings", lambda: settings)
    monkeypatch.setattr(top_down_module, "GeminiProvider", Provider)
    monkeypatch.setattr(top_down_module, "StoryGenerator", Orchestrator)
    menu = TopDownMenu(
        input_fn=input_sequence(["1", "Una historia", "0"]),
        output=lambda message: None,
    )
    menu.run()
    assert captured["prompt"] == "Una historia"
    assert captured["provider_options"]["max_retries"] == 4
    assert captured["generator_options"] == {"default_target_words": 1500}


def test_normal_bottom_up_uses_selected_options(tmp_path, maps_dir, monkeypatch) -> None:
    captured = {}

    def run(args):
        captured["args"] = args
        return tmp_path

    monkeypatch.setattr(
        bottom_up_module,
        "run_one",
        run,
    )
    menu = BottomUpMenu(
        input_fn=input_sequence([str(maps_dir / "minimal_room.json"), "2", "42", "50", "n"]),
        output=lambda message: None,
    )
    menu._normal()
    assert captured["args"].seed == 42
    assert captured["args"].tick_limit == 50
    assert captured["args"].no_llm


def test_cancelled_visual_run_does_not_save(maps_dir, monkeypatch) -> None:
    class CancelVisualizer:
        def __init__(self, **kwargs):
            pass

        def run(self, model, *, tick_limit):
            return VisualOutcome(True, None, model)

    menu = BottomUpMenu(
        input_fn=input_sequence(
            [
                str(maps_dir / "minimal_room.json"),
                "2",
                "3",
                "100",
                "n",
                "0.1",
            ]
        ),
        output=lambda message: None,
        visualizer_factory=CancelVisualizer,
    )
    monkeypatch.setattr(
        menu,
        "_save_visual",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not persist")),
    )
    menu._visual()


def test_completed_visual_run_saves_all_artifacts(tmp_path, room, maps_dir, monkeypatch) -> None:
    result, model = run_simulation(room, seed=5, tick_limit=100)
    menu = BottomUpMenu(output=lambda message: None)
    monkeypatch.setattr(
        bottom_up_module,
        "load_bottom_up_settings",
        lambda: BottomSettings(None, "fake", tmp_path),
    )
    args = argparse.Namespace(
        map=maps_dir / "minimal_room.json",
        agents=2,
        tick_limit=100,
        no_llm=True,
    )
    output = menu._save_visual(args=args, seed=5, room=room, model=model)
    assert result.success
    assert {
        "request.json",
        "initial_world.json",
        "characters.json",
        "ticks.jsonl",
        "events.json",
        "result.json",
        "metrics.json",
        "story.md",
        "story.mp3",
        "audio.json",
        "evaluation.json",
        "metadata.json",
    } <= {path.name for path in output.iterdir()}


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
