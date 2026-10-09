import json
from types import SimpleNamespace
from unittest.mock import create_autospec

from asg_console import evaluation as evaluation_module
from asg_console import stagecraft as stagecraft_module
from asg_console.app import ConsoleApp, StagecraftMenu
from asg_stagecraft import GenerationOptions, StoryGenerator
from asg_stagecraft.formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from asg_stagecraft.runtime import provider as stagecraft_provider_module
from asg_stagecraft.runtime.config import Settings


class MenuSpy:
    def __init__(self) -> None:
        self.calls = 0

    def run(self) -> None:
        self.calls += 1


def input_sequence(values):
    iterator = iter(values)
    return lambda prompt="": next(iterator)


def console_settings(tmp_path, **changes) -> Settings:
    """Real settings, so a field the menu or the provider factory reads cannot go missing."""
    values = {
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
        "promise_ledger": True,
        "story_format": StoryFormat.NARRATIVE,
        "script_method": ScriptMethod.NATIVE,
        "narrative_voice": NarrativeVoice.OMNISCIENT,
        "actor_memory": ActorMemory.OWN,
        "turns_per_beat": 8,
    }
    return Settings(**{**values, **changes})


def test_main_menu_navigates_both_menus_and_rejects_bad_input() -> None:
    stagecraft = MenuSpy()
    evaluation = MenuSpy()
    messages = []
    application = ConsoleApp(
        input_fn=input_sequence(["1", "2", "3", "x", "0"]),
        output=messages.append,
        stagecraft=stagecraft,
        evaluation=evaluation,
    )
    assert application.run() == 0
    assert stagecraft.calls == 1
    assert evaluation.calls == 1
    assert messages.count("Opción inválida.") == 2


def test_stagecraft_passes_prompt_to_orchestrator(tmp_path, monkeypatch) -> None:
    captured = {}

    class Provider:
        def __init__(self, api_key, model, **kwargs):
            self.model_name = model
            captured["provider_options"] = kwargs

    def build_generator(provider, output_root, options):
        captured["generator_options"] = options
        instance = create_autospec(StoryGenerator, spec_set=True, instance=True)

        def generate(request, on_progress=None, on_run_created=None, on_event=None):
            captured["prompt"] = request
            return SimpleNamespace(run_dir=tmp_path)

        instance.generate.side_effect = generate
        return instance

    Orchestrator = create_autospec(StoryGenerator, spec_set=True)
    Orchestrator.from_options.side_effect = build_generator

    settings = console_settings(tmp_path)
    monkeypatch.setattr(stagecraft_module, "load_stagecraft_settings", lambda: settings)
    monkeypatch.setattr(stagecraft_provider_module, "GeminiProvider", Provider)
    monkeypatch.setattr(stagecraft_module, "StoryGenerator", Orchestrator)
    menu = StagecraftMenu(
        input_fn=input_sequence(["1", "Una historia", "", "0"]),
        output=lambda message: None,
    )
    menu.run()
    assert captured["prompt"] == "Una historia"
    assert captured["provider_options"]["max_retries"] == 4
    # The fake settings hold every default, so the options must be the defaults exactly.
    assert captured["generator_options"] == GenerationOptions()


def test_stagecraft_accepts_a_script_output_choice(tmp_path, monkeypatch) -> None:
    captured = {}

    class Provider:
        def __init__(self, api_key, model, **kwargs):
            self.model_name = model

    def build_generator(provider, output_root, options):
        captured["generator_options"] = options
        instance = create_autospec(StoryGenerator, spec_set=True, instance=True)

        def generate(request, on_progress=None, on_run_created=None, on_event=None):
            return SimpleNamespace(run_dir=tmp_path)

        instance.generate.side_effect = generate
        return instance

    Orchestrator = create_autospec(StoryGenerator, spec_set=True)
    Orchestrator.from_options.side_effect = build_generator

    settings = console_settings(tmp_path)
    monkeypatch.setattr(stagecraft_module, "load_stagecraft_settings", lambda: settings)
    monkeypatch.setattr(stagecraft_provider_module, "GeminiProvider", Provider)
    monkeypatch.setattr(stagecraft_module, "StoryGenerator", Orchestrator)
    menu = StagecraftMenu(
        input_fn=input_sequence(["1", "Una historia", "3", "0"]),
        output=lambda message: None,
    )
    menu.run()
    assert captured["generator_options"].story_format is StoryFormat.SCRIPT
    assert captured["generator_options"].script_method is ScriptMethod.ADAPTED


def test_console_evaluates_story_and_retries_invalid_values(tmp_path, monkeypatch) -> None:
    story = tmp_path / "Stories" / "Top-Down" / "story-one"
    story.mkdir(parents=True)
    (story / "story.md").write_text("# Historia", encoding="utf-8")
    retired = tmp_path / "Stories" / "Bottom-Up" / "escape-room"
    retired.mkdir(parents=True)
    (retired / "story.md").write_text("A compartió sus descubrimientos con B.", encoding="utf-8")
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
        stagecraft=MenuSpy(),
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
    assert not (retired / "evaluation.json").exists()
    assert not any("Bottom-Up" in message for message in messages)
    assert "Selección inválida." in messages
    assert "El usuario no puede estar vacío." in messages
    assert "Introduce un entero entre 1 y 10." in messages


def test_stagecraft_asks_who_a_limited_voice_follows(tmp_path, monkeypatch) -> None:
    captured = {}

    class Provider:
        def __init__(self, api_key, model, **kwargs):
            self.model_name = model

    def build_generator(provider, output_root, options):
        captured["generator_options"] = options
        instance = create_autospec(StoryGenerator, spec_set=True, instance=True)

        def generate(request, on_progress=None, on_run_created=None, on_event=None):
            return SimpleNamespace(run_dir=tmp_path)

        instance.generate.side_effect = generate
        return instance

    Orchestrator = create_autospec(StoryGenerator, spec_set=True)
    Orchestrator.from_options.side_effect = build_generator
    settings = console_settings(tmp_path)
    monkeypatch.setattr(stagecraft_module, "load_stagecraft_settings", lambda: settings)
    monkeypatch.setattr(stagecraft_provider_module, "GeminiProvider", Provider)
    monkeypatch.setattr(stagecraft_module, "StoryGenerator", Orchestrator)
    # Output 4 is the simulated story, and voice 3 the third person limited to one character.
    menu = StagecraftMenu(
        input_fn=input_sequence(["1", "Una historia", "4", "3", "Ana", "0"]),
        output=lambda message: None,
    )
    menu.run()
    options = captured["generator_options"]
    assert options.story_format is StoryFormat.SIMULATED
    assert options.narrative_voice is NarrativeVoice.LIMITED
    assert options.narrator == "Ana"


def test_a_simulated_run_announces_the_performance_model(tmp_path, monkeypatch) -> None:
    captured = {}

    class Provider:
        def __init__(self, api_key, model, **kwargs):
            self.model_name = model

    def build_generator(provider, output_root, options):
        captured["provider"] = provider
        instance = create_autospec(StoryGenerator, spec_set=True, instance=True)
        instance.generate.return_value = SimpleNamespace(run_dir=tmp_path)
        return instance

    Orchestrator = create_autospec(StoryGenerator, spec_set=True)
    Orchestrator.from_options.side_effect = build_generator
    settings = console_settings(tmp_path, stage_model="gemini-3.1-flash-lite")
    monkeypatch.setattr(stagecraft_module, "load_stagecraft_settings", lambda: settings)
    monkeypatch.setattr(stagecraft_provider_module, "GeminiProvider", Provider)
    monkeypatch.setattr(stagecraft_module, "StoryGenerator", Orchestrator)
    messages = []
    # Output 4 is the simulated story; an empty answer keeps the omniscient voice.
    menu = StagecraftMenu(
        input_fn=input_sequence(["1", "Una historia", "4", "", "0"]),
        output=messages.append,
    )
    menu.run()
    assert "Generando con fake (función: gemini-3.1-flash-lite)..." in messages
    assert isinstance(captured["provider"], stagecraft_provider_module.RoutedProvider)
    assert captured["provider"].stage_model_name == "gemini-3.1-flash-lite"
