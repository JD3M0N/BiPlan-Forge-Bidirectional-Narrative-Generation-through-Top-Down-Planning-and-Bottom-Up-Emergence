from asg_stagecraft.formats import FORMAT_COST_HINTS, OUTPUT_CHOICES, StoryFormat


def test_every_output_choice_has_a_description() -> None:
    for choice in OUTPUT_CHOICES:
        assert choice.description


def test_every_story_format_has_a_cost_hint() -> None:
    assert set(FORMAT_COST_HINTS) == set(StoryFormat)
