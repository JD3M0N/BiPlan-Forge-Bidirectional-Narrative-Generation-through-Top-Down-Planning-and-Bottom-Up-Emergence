from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from asg_telegram import generators as generators_module
from asg_telegram.contract import (
    GenerationEvent,
    GenerationFailure,
    GenerationProgress,
    StoryGeneratorAdapter,
)
from asg_top_down import StoryGenerator
from asg_top_down.errors import ArtifactValidationError
from asg_top_down.profiles import NarrativeProfile
from asg_top_down.progress import PipelineEvent, ProgressUpdate


def _patch_facade(monkeypatch, tmp_path, captured):
    def build(provider, output_root, **kwargs):
        captured["provider"] = provider
        captured["output_root"] = output_root
        captured["options"] = kwargs
        instance = create_autospec(StoryGenerator, spec_set=True, instance=True)

        def generate(request, on_progress=None, on_run_created=None, on_event=None):
            captured["prompt"] = request
            captured["on_run_created"] = on_run_created
            if on_progress is not None:
                on_progress(ProgressUpdate(40, "writing", "Escribiendo el capítulo 2"))
            if on_event is not None:
                on_event(PipelineEvent(kind="retry", message="Reintento 1", stage="writing"))
            return SimpleNamespace(run_dir=tmp_path)

        instance.generate.side_effect = generate
        return instance

    facade = create_autospec(StoryGenerator, spec_set=True)
    facade.side_effect = build
    provider = object()
    settings = SimpleNamespace(output_root=tmp_path, narrative_guidance=True, model="fake")
    monkeypatch.setattr(generators_module, "StoryGenerator", facade)
    monkeypatch.setattr(generators_module, "load_top_down_settings", lambda: settings)
    monkeypatch.setattr(generators_module, "provider_from_settings", lambda _: provider)
    return provider


def test_adapter_only_calls_methods_the_real_facade_defines(tmp_path, monkeypatch):
    captured: dict = {}
    provider = _patch_facade(monkeypatch, tmp_path, captured)
    run_created = object()
    progress: list = []
    events: list = []

    run_dir = generators_module.TopDownGenerator().generate(
        "Una historia sobre un faro",
        on_progress=progress.append,
        on_run_created=run_created,
        on_event=events.append,
    )

    assert run_dir == tmp_path
    assert captured["prompt"] == "Una historia sobre un faro"
    assert captured["provider"] is provider
    assert captured["output_root"] == tmp_path
    assert captured["options"] == {"narrative_guidance": True, "narrative_profile": None}
    assert captured["on_run_created"] is run_created
    assert progress == [GenerationProgress(40, "writing", "Escribiendo el capítulo 2")]
    assert events == [GenerationEvent("Reintento 1", "writing")]


def test_adapter_forwards_the_narrative_guidance_setting(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    settings = SimpleNamespace(output_root=tmp_path, narrative_guidance=False, model="fake")
    monkeypatch.setattr(generators_module, "load_top_down_settings", lambda: settings)

    generators_module.TopDownGenerator().generate("Otra historia")

    assert captured["options"] == {"narrative_guidance": False, "narrative_profile": None}


def test_adapter_forwards_the_chosen_narrative_profile(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)

    generators_module.TopDownGenerator().generate("Una historia", narrative_profile="essential")

    assert captured["options"]["narrative_profile"] is NarrativeProfile.ESSENTIAL


def test_adapter_translates_pipeline_errors_into_application_failures(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    error = ArtifactValidationError("No se pudo completar el capítulo 1.", stage="planning")
    error.run_id = "run-7"

    def explode(*args, **kwargs):
        raise error

    monkeypatch.setattr(
        generators_module,
        "StoryGenerator",
        lambda *args, **kwargs: SimpleNamespace(generate=explode),
    )

    with pytest.raises(GenerationFailure) as raised:
        generators_module.TopDownGenerator().generate("Una historia")

    failure = raised.value
    assert failure.code == "ARTIFACT_VALIDATION_FAILED"
    assert failure.stage == "planning"
    assert failure.run_id == "run-7"
    assert "ARTIFACT_VALIDATION_FAILED" in failure.public_message()


def test_the_real_adapter_satisfies_the_application_contract(tmp_path, monkeypatch):
    _patch_facade(monkeypatch, tmp_path, {})
    assert isinstance(generators_module.TopDownGenerator(), StoryGeneratorAdapter)
