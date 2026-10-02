import pytest
from asg_stagecraft import GenerationOptions
from asg_stagecraft.brief import MAX_CAST
from asg_stagecraft.formats import FORMAT_COST_HINTS, NarrativeVoice
from asg_studio.catalog import SET_BY_PRESET, available_keys, catalog_document, pending_keys
from pydantic import ValidationError


def document():
    return catalog_document(GenerationOptions())


def test_every_available_control_sets_a_real_option() -> None:
    fields = set(GenerationOptions.model_fields)
    keys = available_keys(document()) - {"output"}
    assert keys <= fields
    # Every option a run can take is either a control or set by the format preset.
    assert fields - keys == SET_BY_PRESET


def test_pending_controls_are_not_options_and_are_rejected() -> None:
    pending = pending_keys(document())
    assert pending == {"plan_from", "multi_voice"}
    assert not pending & set(GenerationOptions.model_fields)
    for key in pending:
        with pytest.raises(ValidationError):
            GenerationOptions(**{key: True})


def test_pending_choices_are_visible_but_not_valid_values() -> None:
    groups = {group["id"]: group for group in document()["groups"]}
    voices = groups["narration"]["options"][0]["choices"]
    pending = [choice["value"] for choice in voices if choice.get("status") == "pending"]
    assert pending == ["spoiler_safe"]
    with pytest.raises(ValueError):
        NarrativeVoice("spoiler_safe")
    memories = groups["simulation"]["options"][0]["choices"]
    assert [choice["value"] for choice in memories] == ["own", "shared", "full"]
    with pytest.raises(ValidationError):
        GenerationOptions(actor_memory="full")


def test_the_character_control_follows_the_voices_told_from_one() -> None:
    groups = {group["id"]: group for group in document()["groups"]}
    narrator = groups["narration"]["options"][1]
    assert narrator["kind"] == "character"
    assert set(narrator["enabled_when"]["narrative_voice"]) == {"limited", "first_person"}


def test_every_audio_voice_is_offered_once_after_the_automatic_one() -> None:
    groups = {group["id"]: group for group in document()["groups"]}
    voice = groups["audio"]["options"][1]
    values = [choice["value"] for group in voice["groups"] for choice in group["choices"]]
    assert values[0] == ""
    assert len(values) == len(set(values)) == 46


def test_available_option_labels_match_the_generator_field_metadata() -> None:
    doc = document()
    fields = GenerationOptions.model_fields
    for group in doc["groups"]:
        for option in group["options"]:
            if option["status"] != "available" or option["key"] not in fields:
                continue
            field = fields[option["key"]]
            assert option["label"] == field.title
            assert option["help"] == field.description


def test_cost_hints_match_the_generator_and_max_cast_matches_the_brief() -> None:
    doc = document()
    assert doc["cost"] == {fmt.value: hint for fmt, hint in FORMAT_COST_HINTS.items()}
    assert doc["brief"]["max_cast"] == MAX_CAST


def test_the_format_preset_sets_both_the_format_and_the_method() -> None:
    groups = {group["id"]: group for group in document()["groups"]}
    presets = groups["format"]["options"][0]["choices"]
    assert {choice["value"] for choice in presets} == {
        "narrative",
        "script-native",
        "script-adapted",
        "simulated",
    }
    for choice in presets:
        assert set(choice["sets"]) == {"story_format", "script_method"}
        GenerationOptions(**choice["sets"])
