import pytest
from asg_telegram.wizard import (
    BRIEF_STEPS,
    check_length,
    outline_from,
    outline_summary,
    question,
)
from telegram_fakes import BRIEF_SPEC


def test_brief_steps_put_the_plot_before_the_cast():
    assert BRIEF_STEPS.index("plot") < BRIEF_STEPS.index("cast")
    assert BRIEF_STEPS[-1] == "confirm"


def test_question_states_the_declared_length_limit():
    assert "4000" in question("plot", BRIEF_SPEC)


def test_check_length_trims_and_rejects_overlong_text():
    assert check_length("title", "  Un título  ", BRIEF_SPEC) == "Un título"
    with pytest.raises(ValueError, match="80"):
        check_length("name", "x" * 81, BRIEF_SPEC)


def test_outline_from_builds_a_cast_from_plain_dicts():
    outline = outline_from(
        {
            "plot": "Una trama",
            "cast": [{"name": "Ana", "role": "protagonista", "pronoun": "ella"}],
        }
    )
    assert outline.plot == "Una trama"
    assert outline.cast[0].name == "Ana"


def test_outline_summary_stays_under_telegrams_message_limit():
    outline = outline_from({"plot": "x" * 4000, "notes": "y" * 1500})
    summary = outline_summary(outline, limit=3500)
    assert len(summary) <= 3500
