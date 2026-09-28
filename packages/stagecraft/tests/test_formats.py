import pytest
from asg_stagecraft.formats import (
    FORMAT_COST_HINTS,
    OUTPUT_CHOICES,
    ScriptMethod,
    StoryFormat,
    output_choice,
    output_choice_for,
)


def test_narrative_ignores_the_script_method_but_script_matches_it() -> None:
    assert output_choice(StoryFormat.NARRATIVE, ScriptMethod.ADAPTED) == OUTPUT_CHOICES[0]
    choice = output_choice(StoryFormat.SCRIPT, ScriptMethod.ADAPTED)
    assert choice.key == "script-adapted"
    assert choice.script_method is ScriptMethod.ADAPTED


def test_output_choice_for_returns_every_key_with_a_description() -> None:
    for choice in OUTPUT_CHOICES:
        assert output_choice_for(choice.key) is choice
        assert choice.description


def test_output_choice_for_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="stage-play"):
        output_choice_for("stage-play")


def test_every_story_format_has_a_cost_hint() -> None:
    assert set(FORMAT_COST_HINTS) == set(StoryFormat)
