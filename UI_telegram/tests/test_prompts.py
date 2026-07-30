import pytest

from asg_telegram.prompts import (
    METRIC_EXPLANATIONS,
    build_guided_prompt,
    split_story,
    validate_guided_value,
)


def guided_values():
    return {
        "language": "español",
        "genre": "fantasía",
        "protagonist": "una cartógrafa",
        "conflict": "las estrellas desaparecen",
        "setting": "una estación orbital",
        "tone": "melancólico",
        "target_words": "1500",
        "constraints": "ninguna",
    }


def test_guided_prompt_contains_every_answer():
    prompt = build_guided_prompt(guided_values())
    assert prompt == (
        "Escribe una historia en español de aproximadamente 1500 palabras. "
        "Género: fantasía. Protagonista: una cartógrafa. Conflicto principal: "
        "las estrellas desaparecen. Ambientación: una estación orbital. "
        "Tono: melancólico. Restricciones: Sin restricciones adicionales."
    )


@pytest.mark.parametrize("value", ["299", "20001", "mil", ""])
def test_target_words_are_validated(value):
    with pytest.raises(ValueError):
        validate_guided_value("target_words", value)


def test_story_split_preserves_text_content():
    text = "Primer párrafo.\n\n" + ("palabra " * 100) + "\n\nFinal."
    chunks = split_story(text, limit=80)
    assert all(len(chunk) <= 80 for chunk in chunks)
    assert "".join(chunks).replace("\n", "").replace(" ", "") == (
        text.replace("\n", "").replace(" ", "")
    )


def test_all_evaluation_metrics_have_spanish_explanations():
    assert set(METRIC_EXPLANATIONS) == {
        "coherence",
        "pacing",
        "creativity",
        "engagement",
        "relevance",
        "satisfaction",
    }
    assert all(":" in explanation for explanation in METRIC_EXPLANATIONS.values())
