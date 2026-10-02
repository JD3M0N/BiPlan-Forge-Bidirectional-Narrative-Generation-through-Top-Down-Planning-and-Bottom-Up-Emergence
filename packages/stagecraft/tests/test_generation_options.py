import dataclasses
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest
from asg_stagecraft import GenerationOptions, StoryGenerator
from asg_stagecraft import pipeline as pipeline_module
from asg_stagecraft.formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from asg_stagecraft.planning.profiles import NarrativeProfile
from asg_stagecraft.runtime.config import Settings, load_settings
from pydantic import ValidationError
from test_generator_v5 import FakeProvider, make_request


def project(tmp_path):
    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    return tmp_path


def test_the_facade_keywords_mirror_the_options_exactly() -> None:
    """A new option needs a facade keyword too: autospec'd surfaces are checked against it."""
    parameters = inspect.signature(StoryGenerator.__init__).parameters
    keywords = {
        name: parameter.default
        for name, parameter in parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    }
    fields = {name: field.default for name, field in GenerationOptions.model_fields.items()}
    assert keywords == fields


def test_every_default_shared_with_settings_agrees() -> None:
    defaults = {
        field.name: field.default
        for field in dataclasses.fields(Settings)
        if field.default is not dataclasses.MISSING
    }
    options = GenerationOptions()
    shared = set(defaults) & set(GenerationOptions.model_fields)
    assert shared, "the options and the settings no longer share any field"
    for name in shared:
        assert getattr(options, name) == defaults[name], name


def test_options_reject_unknown_fields_and_cannot_change() -> None:
    with pytest.raises(ValidationError):
        GenerationOptions(weather="lluvia")
    options = GenerationOptions()
    with pytest.raises(ValidationError):
        options.turns_per_beat = 3
    with pytest.raises(ValidationError):
        GenerationOptions(turns_per_beat=1)


@pytest.mark.parametrize(
    ("build", "match"),
    [
        (lambda: GenerationOptions(audio_voice="es-XX-NadieNeural"), None),
        (
            lambda: GenerationOptions(narrative_voice=NarrativeVoice.OMNISCIENT, narrator="Ana"),
            "personaje",
        ),
        (lambda: GenerationOptions(narration_tone="x" * 301), None),
    ],
    ids=["unknown-audio-voice", "narrator-without-a-voice-that-follows-one", "tone-too-long"],
)
def test_more_invalid_options_are_rejected(build, match) -> None:
    with pytest.raises(ValidationError, match=match):
        build()


def test_options_normalize_whitespace_around_the_audio_voice_and_the_narrator() -> None:
    assert GenerationOptions(audio_voice=" es-MX-JorgeNeural ").audio_voice == "es-MX-JorgeNeural"
    options = GenerationOptions(
        narrative_voice=NarrativeVoice.LIMITED, narrator="  Ana \n Vela ", narration_tone="seco"
    )
    assert options.narrator == "Ana Vela"


def test_settings_supply_defaults_and_flags_override_them() -> None:
    settings = SimpleNamespace(
        api_key="secret",
        story_format=StoryFormat.SCRIPT,
        script_method=ScriptMethod.ADAPTED,
        narrative_guidance=False,
        promise_ledger=True,
        narrative_voice=NarrativeVoice.FOCALIZED,
        actor_memory=ActorMemory.SHARED,
        turns_per_beat=5,
    )
    options = GenerationOptions.from_settings(
        settings, story_format=StoryFormat.SIMULATED, actor_memory=None
    )
    assert options.story_format is StoryFormat.SIMULATED
    # None keeps what the settings said, so an unset flag can be passed straight through.
    assert options.actor_memory is ActorMemory.SHARED
    assert options.narrative_guidance is False
    assert options.turns_per_beat == 5
    assert options.narrative_profile is None
    with pytest.raises(TypeError, match="weather"):
        GenerationOptions.from_settings(settings, weather="lluvia")


def test_with_changes_revalidates_and_rejects_unknown_names() -> None:
    options = GenerationOptions().with_changes(narrative_profile=NarrativeProfile.ESSENTIAL)
    assert options.narrative_profile is NarrativeProfile.ESSENTIAL
    with pytest.raises(ValidationError):
        options.with_changes(turns_per_beat=0)
    with pytest.raises(TypeError, match="weather"):
        options.with_changes(weather="lluvia")


def test_the_facade_built_from_options_carries_them_unchanged(tmp_path) -> None:
    options = GenerationOptions(
        story_format=StoryFormat.SIMULATED,
        narrative_voice=NarrativeVoice.FIRST_PERSON,
        turns_per_beat=4,
    )
    generator = StoryGenerator.from_options(object(), tmp_path, options)
    assert generator.options == options
    assert StoryGenerator(object(), tmp_path).options == GenerationOptions()


def test_settings_load_without_a_key_when_the_caller_only_reads_options(
    tmp_path, monkeypatch
) -> None:
    root = project(tmp_path)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("ASG_STORY_FORMAT", "simulated")
    settings = load_settings(root, require_api_key=False)
    assert settings.api_key == ""
    assert GenerationOptions.from_settings(settings).story_format is StoryFormat.SIMULATED


def test_the_audio_voice_reaches_the_audio_step_only_when_chosen(tmp_path, monkeypatch) -> None:
    calls = []

    def create(story_path, **kwargs):
        calls.append(kwargs)
        audio = Path(story_path).with_suffix(".mp3")
        audio.write_bytes(b"fake-mp3")
        return SimpleNamespace(path=audio, language="es", voice=kwargs.get("voice", "auto"))

    monkeypatch.setattr(pipeline_module, "create_story_audio_sync", create)
    StoryGenerator(FakeProvider(), tmp_path / "auto").generate(make_request())
    StoryGenerator(FakeProvider(), tmp_path / "chosen", audio_voice="es-CU-BelkysNeural").generate(
        make_request()
    )
    # Without a choice the call is exactly the one every run made before 7.3.
    assert calls == [{}, {"voice": "es-CU-BelkysNeural"}]


def test_every_interface_facing_field_has_a_spanish_label_and_help() -> None:
    """Studio and Telegram read title/description instead of duplicating the strings."""
    hidden = {"story_format", "script_method"}
    for name, field in GenerationOptions.model_fields.items():
        if name in hidden:
            continue
        assert field.title, name
        assert field.description, name
