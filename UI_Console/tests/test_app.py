import argparse
import json
from pathlib import Path

from asg_console import app
from asg_console.app import BottomUpMenu, ConsoleApp, TopDownMenu
from asg_console.visualizer import VisualOutcome
from asg_escape_room import EscapeRoomModel, run_simulation
from asg_escape_room.config import Settings as BottomSettings
from asg_prompt_crafter import CraftResult, PromptAlternative


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
        def __init__(self, api_key, model):
            self.model_name = model

    class Orchestrator:
        def __init__(self, provider, output_root, default_target_words=1500):
            pass

        def run(self, prompt):
            captured["prompt"] = prompt
            return tmp_path

    settings = type(
        "Settings",
        (),
        {
            "api_key": "test", "model": "fake", "output_root": tmp_path,
            "default_target_words": 1500,
        },
    )()
    monkeypatch.setattr(app, "load_top_down_settings", lambda: settings)
    monkeypatch.setattr(app, "GeminiProvider", Provider)
    monkeypatch.setattr(app, "StoryGenerator", Orchestrator)
    menu = TopDownMenu(
        input_fn=input_sequence(["1", "2", "Una historia", "0"]),
        output=lambda message: None,
    )
    menu.run()
    assert captured["prompt"] == "Una historia"


def test_top_down_assisted_prompt_uses_selected_alternative(
    tmp_path, monkeypatch
) -> None:
    captured = {}

    class Provider:
        def __init__(self, api_key, model):
            self.model_name = model

    class Crafter:
        def __init__(self, provider):
            captured["crafter_provider"] = provider

        def craft(self, prompt):
            captured["idea"] = prompt
            return CraftResult(
                original_prompt=prompt,
                alternatives=[
                    PromptAlternative(
                        id="one",
                        name="Primera",
                        creative_direction="Dirección uno",
                        prompt="Prompt enriquecido uno",
                    ),
                    PromptAlternative(
                        id="two",
                        name="Segunda",
                        creative_direction="Dirección dos",
                        prompt="Prompt enriquecido dos",
                    ),
                    PromptAlternative(
                        id="three",
                        name="Tercera",
                        creative_direction="Dirección tres",
                        prompt="Prompt enriquecido tres",
                    ),
                ],
                recommended_id="two",
                recommendation_reason="Es la más sólida.",
            )

    class Orchestrator:
        def __init__(self, provider, output_root, default_target_words=1500):
            captured["orchestrator_provider"] = provider

        def run(self, prompt):
            captured["prompt"] = prompt
            return tmp_path

    settings = type(
        "Settings",
        (),
        {
            "api_key": "test", "model": "fake", "output_root": tmp_path,
            "default_target_words": 1500,
        },
    )()
    monkeypatch.setattr(app, "load_top_down_settings", lambda: settings)
    monkeypatch.setattr(app, "GeminiProvider", Provider)
    monkeypatch.setattr(app, "PromptCrafterAgent", Crafter)
    monkeypatch.setattr(app, "StoryGenerator", Orchestrator)
    messages = []
    menu = TopDownMenu(
        input_fn=input_sequence(["1", "1", "Idea breve", "x", "2", "0"]),
        output=messages.append,
    )

    menu.run()

    assert captured["idea"] == "Idea breve"
    assert captured["prompt"] == "Prompt enriquecido dos"
    assert captured["crafter_provider"] is captured["orchestrator_provider"]
    assert any("Segunda [two] — RECOMENDADA" in message for message in messages)
    assert "Selección inválida." in messages


def test_top_down_can_cancel_assisted_selection(monkeypatch) -> None:
    class UnexpectedOrchestrator:
        def __init__(self, provider, output_root):
            raise AssertionError("No debe generar una historia")

    class Provider:
        model_name = "fake"

        def __init__(self, api_key, model):
            pass

    class Crafter:
        def __init__(self, provider):
            pass

        def craft(self, prompt):
            alternatives = [
                PromptAlternative(
                    id=str(index),
                    name=f"Opción {index}",
                    creative_direction="Dirección",
                    prompt=f"Prompt {index}",
                )
                for index in range(1, 4)
            ]
            return CraftResult(
                original_prompt=prompt,
                alternatives=alternatives,
                recommended_id="1",
                recommendation_reason="Razón",
            )

    settings = type(
        "Settings",
        (),
        {"api_key": "test", "model": "fake", "output_root": Path()},
    )()
    monkeypatch.setattr(app, "load_top_down_settings", lambda: settings)
    monkeypatch.setattr(app, "GeminiProvider", Provider)
    monkeypatch.setattr(app, "PromptCrafterAgent", Crafter)
    monkeypatch.setattr(app, "StoryGenerator", UnexpectedOrchestrator)
    menu = TopDownMenu(
        input_fn=input_sequence(["1", "1", "Idea", "0", "0"]),
        output=lambda message: None,
    )

    menu.run()


def test_normal_bottom_up_uses_selected_options(maps_dir, monkeypatch) -> None:
    captured = {}
    monkeypatch.setattr(
        app, "run_one", lambda args: captured.setdefault("args", args) or Path()
    )
    menu = BottomUpMenu(
        input_fn=input_sequence(
            [str(maps_dir / "minimal_room.json"), "2", "42", "50", "n"]
        ),
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
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("must not persist")
        ),
    )
    menu._visual()


def test_completed_visual_run_saves_all_artifacts(
    tmp_path, room, maps_dir, monkeypatch
) -> None:
    result, model = run_simulation(room, seed=5, tick_limit=100)
    menu = BottomUpMenu(output=lambda message: None)
    monkeypatch.setattr(
        app,
        "load_bottom_up_settings",
        lambda: BottomSettings(None, "fake", tmp_path),
    )
    args = argparse.Namespace(
        map=maps_dir / "minimal_room.json",
        agents=2,
        tick_limit=100,
        no_llm=True,
    )
    output = menu._save_visual(
        args=args, seed=5, room=room, model=model
    )
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
        "evaluation.json",
        "metadata.json",
    } <= {path.name for path in output.iterdir()}


def test_console_evaluates_story_and_retries_invalid_values(
    tmp_path, monkeypatch
) -> None:
    story = tmp_path / "Stories" / "Top-Down" / "story-one"
    story.mkdir(parents=True)
    (story / "story.md").write_text("# Historia", encoding="utf-8")
    monkeypatch.setattr(app, "find_project_root", lambda: tmp_path)
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
    document = json.loads(
        (story / "evaluation.json").read_text(encoding="utf-8")
    )
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
