from asg_telegram.panel import (
    choice_keyboard,
    describe_options,
    group_keyboard,
    panel_keyboard,
    parse_callback,
    value_label,
    visible_specs,
)
from telegram_fakes import AUDIO_VOICE_SPEC, DEFAULT_OPTIONS, OPTION_SPECS


def test_simulated_only_options_are_hidden_for_narrative():
    values = dict(DEFAULT_OPTIONS)
    visible = {spec.key for spec in visible_specs(OPTION_SPECS, values)}
    assert "narrative_voice" not in visible
    values["format"] = "simulated"
    visible = {spec.key for spec in visible_specs(OPTION_SPECS, values)}
    assert "narrative_voice" in visible


def test_narrator_only_shows_up_for_the_voices_that_take_a_character():
    values = {**DEFAULT_OPTIONS, "format": "simulated", "narrative_voice": "omniscient"}
    assert "narrator" not in {spec.key for spec in visible_specs(OPTION_SPECS, values)}
    values["narrative_voice"] = "first_person"
    assert "narrator" in {spec.key for spec in visible_specs(OPTION_SPECS, values)}


def test_value_label_covers_every_kind():
    assert value_label(next(s for s in OPTION_SPECS if s.key == "audio"), True) == "activado"
    assert value_label(next(s for s in OPTION_SPECS if s.key == "turns_per_beat"), 8) == "8"
    format_spec = next(s for s in OPTION_SPECS if s.key == "format")
    assert value_label(format_spec, "narrative") == "Historia narrativa"


def test_describe_options_excludes_the_format_itself():
    text = describe_options(OPTION_SPECS, DEFAULT_OPTIONS)
    assert "Formato de salida" not in text
    assert "Ledger de promesas" in text


def test_panel_keyboard_has_a_button_per_visible_option_plus_reset_and_done():
    markup = panel_keyboard(OPTION_SPECS, DEFAULT_OPTIONS)
    callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
    assert "opt:reset" in callbacks
    assert "opt:done" in callbacks
    assert any(cb.startswith("opt:tog:promise_ledger") for cb in callbacks)


def test_audio_voice_choice_keyboard_groups_by_country():
    markup = choice_keyboard(AUDIO_VOICE_SPEC, DEFAULT_OPTIONS)
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert "México" in labels
    assert "España" in labels


def test_group_keyboard_lists_only_that_countrys_voices():
    markup = group_keyboard(AUDIO_VOICE_SPEC, DEFAULT_OPTIONS, 0)
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert any("Dalia" in label for label in labels)
    assert not any("Álvaro" in label for label in labels)


def test_every_panel_callback_fits_telegrams_64_byte_limit():
    markup = panel_keyboard(OPTION_SPECS, DEFAULT_OPTIONS)
    for row in markup.inline_keyboard:
        for button in row:
            assert len(button.callback_data.encode("utf-8")) <= 64


def test_parse_callback_splits_action_key_and_extra():
    assert parse_callback("opt:home") == ("home", None, None)
    assert parse_callback("opt:set:audio_voice:3") == ("set", "audio_voice", "3")
