from asg_stagecraft.formats import (
    FORMAT_COST_HINTS,
    OUTPUT_CHOICES,
    ScriptMethod,
    StoryFormat,
    output_choice,
    output_choice_for,
)


def test_narrative_ignores_the_script_method() -> None:
    assert output_choice(StoryFormat.NARRATIVE, ScriptMethod.ADAPTED) == OUTPUT_CHOICES[0]


def test_output_choice_finds_the_matching_script_method() -> None:
    choice = output_choice(StoryFormat.SCRIPT, ScriptMethod.ADAPTED)
    assert choice.key == "script-adapted"
    assert choice.script_method is ScriptMethod.ADAPTED


def test_output_choice_for_returns_every_key() -> None:
    for choice in OUTPUT_CHOICES:
        assert output_choice_for(choice.key) is choice


def test_output_choice_for_rejects_unknown_key() -> None:
    try:
        output_choice_for("stage-play")
    except ValueError as exc:
        assert "stage-play" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_every_output_choice_has_a_description() -> None:
    for choice in OUTPUT_CHOICES:
        assert choice.description


def test_every_story_format_has_a_cost_hint() -> None:
    assert set(FORMAT_COST_HINTS) == set(StoryFormat)
