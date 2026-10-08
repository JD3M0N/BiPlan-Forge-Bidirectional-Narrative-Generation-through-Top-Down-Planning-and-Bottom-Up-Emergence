from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from asg_stagecraft import GenerationOptions, StoryBrief, StoryGenerator
from asg_stagecraft.formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from asg_stagecraft.options import API_ONLY_OPTIONS
from asg_stagecraft.planning.profiles import NarrativeProfile
from asg_stagecraft.runtime.config import Settings
from asg_stagecraft.runtime.errors import PlotValidationError, RunCancelledError
from asg_stagecraft.runtime.progress import PipelineEvent, ProgressUpdate
from asg_telegram import generators as generators_module
from asg_telegram.contract import (
    CastEntry,
    GenerationCancelled,
    GenerationEvent,
    GenerationFailure,
    GenerationProgress,
    StoryOutline,
)


def _patch_facade(
    monkeypatch,
    tmp_path,
    captured,
    *,
    narrative_guidance=True,
    promise_ledger=True,
    story_format=StoryFormat.NARRATIVE,
    script_method=ScriptMethod.NATIVE,
    on_generate=None,
    **setting_changes,
):
    def build(provider, output_root, options):
        captured["provider"] = provider
        captured["output_root"] = output_root
        captured["options"] = options
        instance = create_autospec(StoryGenerator, spec_set=True, instance=True)

        def generate(
            request, on_progress=None, on_run_created=None, on_event=None, should_cancel=None
        ):
            captured["request"] = request
            captured["on_run_created"] = on_run_created
            captured["should_cancel"] = should_cancel
            if on_generate is not None:
                on_generate()
            if on_progress is not None:
                on_progress(ProgressUpdate(40, "writing", "Escribiendo el capítulo 2"))
            if on_event is not None:
                on_event(PipelineEvent(kind="retry", message="Reintento 1", stage="writing"))
            return SimpleNamespace(run_dir=tmp_path)

        instance.generate.side_effect = generate
        return instance

    facade = create_autospec(StoryGenerator, spec_set=True)
    facade.from_options.side_effect = build
    provider = SimpleNamespace(usage_records=[])
    settings = Settings(
        api_key="secret-key",
        model="fake-model",
        output_root=tmp_path,
        rpm_limit=15,
        rpm_reserve=1,
        tpm_limit=0,
        narrative_guidance=narrative_guidance,
        promise_ledger=promise_ledger,
        story_format=story_format,
        script_method=script_method,
        narrative_voice=NarrativeVoice.OMNISCIENT,
        actor_memory=ActorMemory.OWN,
        turns_per_beat=8,
        **setting_changes,
    )
    monkeypatch.setattr(generators_module, "StoryGenerator", facade)
    monkeypatch.setattr(generators_module, "load_stagecraft_settings", lambda: settings)
    monkeypatch.setattr(generators_module, "provider_from_settings", lambda _: provider)
    return provider


def test_generate_passes_normalized_options_and_forwards_callbacks(tmp_path, monkeypatch):
    """`spec_set` autospec rejects any method or option the real facade does not declare."""
    captured: dict = {}
    provider = _patch_facade(monkeypatch, tmp_path, captured)
    run_created = object()
    progress: list = []
    events: list = []

    run_dir = generators_module.StagecraftGenerator().generate(
        "Una historia sobre un faro",
        on_progress=progress.append,
        on_run_created=run_created,
        on_event=events.append,
    )

    assert run_dir == tmp_path
    assert captured["request"] == "Una historia sobre un faro"
    assert captured["provider"] is provider
    assert captured["output_root"] == tmp_path
    assert captured["options"] == GenerationOptions(
        narrative_guidance=True,
        promise_ledger=True,
        narrative_profile=None,
        story_format=StoryFormat.NARRATIVE,
        script_method=ScriptMethod.NATIVE,
        narrative_voice=NarrativeVoice.OMNISCIENT,
        actor_memory=ActorMemory.OWN,
        turns_per_beat=8,
    )
    assert captured["on_run_created"] is run_created
    assert progress == [GenerationProgress(40, "writing", "Escribiendo el capítulo 2")]
    assert events == [GenerationEvent("Reintento 1", "writing", "retry")]


def test_a_chosen_profile_arrives_as_the_pipelines_own_enum(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    generators_module.StagecraftGenerator().generate(
        "Una historia", options={"narrative_profile": "essential"}
    )
    assert captured["options"].narrative_profile is NarrativeProfile.ESSENTIAL


def test_guidance_and_ledger_are_forwarded_not_hardcoded(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured, narrative_guidance=False)
    generators_module.StagecraftGenerator().generate("Otra historia")
    assert captured["options"] == GenerationOptions(narrative_guidance=False)

    _patch_facade(monkeypatch, tmp_path, captured, promise_ledger=False)
    generators_module.StagecraftGenerator().generate("Una tercera historia")
    assert captured["options"].promise_ledger is False


def test_the_output_format_resolves_story_format_and_script_method(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    generators_module.StagecraftGenerator().generate(
        "Una historia", options={"format": "script-adapted"}
    )
    assert captured["options"].story_format is StoryFormat.SCRIPT
    assert captured["options"].script_method is ScriptMethod.ADAPTED


def test_an_unknown_format_is_reported_as_invalid_options(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    with pytest.raises(GenerationFailure) as unknown_format:
        generators_module.StagecraftGenerator().generate(
            "Una historia", options={"format": "stage-play"}
        )
    assert unknown_format.value.code == "INVALID_OPTIONS"


def test_the_shared_provider_forgets_each_finished_job(tmp_path, monkeypatch):
    """MED-2: jobs share one provider, and its usage records grew for as long as the bot ran."""
    captured: dict = {}
    provider = _patch_facade(monkeypatch, tmp_path, captured)
    provider.usage_records.append("a record the previous run already wrote to disk")
    generators_module.StagecraftGenerator().generate("Una historia")
    assert provider.usage_records == []


def test_adapter_translates_pipeline_errors_into_application_failures(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    error = PlotValidationError("No se pudo completar el capítulo 1.")
    error.run_id = "run-7"

    def explode(*args, **kwargs):
        raise error

    monkeypatch.setattr(
        generators_module,
        "StoryGenerator",
        SimpleNamespace(from_options=lambda *args, **kwargs: SimpleNamespace(generate=explode)),
    )

    with pytest.raises(GenerationFailure) as raised:
        generators_module.StagecraftGenerator().generate("Una historia")

    failure = raised.value
    assert failure.code == "PLOT_VALIDATION_FAILED"
    assert failure.stage == "planning"
    assert failure.run_id == "run-7"
    assert "PLOT_VALIDATION_FAILED" in failure.public_message()


def test_should_cancel_is_forwarded_and_run_cancelled_becomes_generation_cancelled(
    tmp_path, monkeypatch
):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)

    def explode(*args, **kwargs):
        raise RunCancelledError("La generación se canceló a petición de quien la lanzó.")

    monkeypatch.setattr(
        generators_module,
        "StoryGenerator",
        SimpleNamespace(from_options=lambda *args, **kwargs: SimpleNamespace(generate=explode)),
    )

    with pytest.raises(GenerationCancelled):
        generators_module.StagecraftGenerator().generate("Una historia", should_cancel=lambda: True)


def test_option_specs_cover_every_generation_options_field_except_the_preset(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    keys = {spec.key for spec in generators_module.StagecraftGenerator().option_specs}
    fields = (
        set(GenerationOptions.model_fields) - {"story_format", "script_method"} - API_ONLY_OPTIONS
    )
    assert keys == fields | {"format"}


def test_narrator_is_dropped_for_voices_not_told_from_one(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    generator = generators_module.StagecraftGenerator()
    normalized = generator.normalize_options({"narrative_voice": "omniscient", "narrator": "Ana"})
    assert normalized["narrator"] == ""


def test_invalid_option_values_are_explained_in_spanish(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    generator = generators_module.StagecraftGenerator()
    with pytest.raises(ValueError, match="turns_per_beat"):
        generator.normalize_options({"turns_per_beat": 1})


def test_unknown_option_keys_are_ignored(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    generator = generators_module.StagecraftGenerator()
    normalized = generator.normalize_options({"weather": "lluvia"})
    assert "weather" not in normalized


def test_outline_reaches_the_pipeline_as_a_story_brief(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    outline = StoryOutline(
        plot="Una archivera descubre un secreto.",
        title="El archivo",
        cast=(CastEntry(name="Ana", role="protagonista", pronoun="ella"),),
    )
    generators_module.StagecraftGenerator().generate(outline)
    assert isinstance(captured["request"], StoryBrief)
    assert captured["request"].title == "El archivo"
    assert captured["request"].cast[0].name == "Ana"


def test_validate_outline_rejects_duplicate_names_with_or_without_accents(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    generator = generators_module.StagecraftGenerator()
    outline = StoryOutline(
        plot="Una trama",
        cast=(CastEntry(name="Ana"), CastEntry(name="ana")),
    )
    with pytest.raises(ValueError, match="reparto"):
        generator.validate_outline(outline)


def test_brief_spec_limits_match_the_story_brief_model(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    spec = generators_module.StagecraftGenerator().brief_spec
    assert spec.limits["plot"] == 4000
    assert spec.max_cast == 10


def test_startup_details_never_show_the_api_key(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(monkeypatch, tmp_path, captured)
    details = generators_module.StagecraftGenerator().startup_details()
    joined = " ".join(f"{label}={value}" for label, value in details)
    assert "secret-key" not in joined
    assert "configurada" in joined
    assert "Modelo de la función" not in joined


def test_startup_details_name_the_performance_model_but_not_its_key(tmp_path, monkeypatch):
    captured: dict = {}
    _patch_facade(
        monkeypatch,
        tmp_path,
        captured,
        stage_model="gemini-3.1-flash-lite",
        stage_api_key="stage-secret",
    )
    details = dict(generators_module.StagecraftGenerator().startup_details())
    assert details["Modelo"] == "fake-model"
    assert details["Modelo de la función"] == "gemini-3.1-flash-lite · 15 RPM · clave propia"
    assert "stage-secret" not in " ".join(details.values())
