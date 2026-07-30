import html
import re

import pytest

from asg_telegram.prompts import (
    METRIC_EXPLANATIONS,
    build_guided_prompt,
    split_story,
    telegram_story_chunks,
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
    assert all(
        explanation.name
        and explanation.description
        and explanation.low
        and explanation.high
        for explanation in METRIC_EXPLANATIONS.values()
    )
    assert "Insatisfecho" in METRIC_EXPLANATIONS["satisfaction"].message()
    assert "Muy satisfecho" in METRIC_EXPLANATIONS["satisfaction"].message()


def test_telegram_story_formats_headings_and_escapes_html():
    markdown = (
        "# La Cartografía del Silencio\n\n"
        "### I. Planteamiento\n\n"
        "Elena observó A < B & C > D."
    )
    chunks = telegram_story_chunks(markdown)
    rendered = "\n\n".join(chunks)
    assert "# " not in rendered
    assert "###" not in rendered
    assert "<b>La Cartografía del Silencio</b>" in rendered
    assert "<b>I. Planteamiento</b>" in rendered
    assert "A &lt; B &amp; C &gt; D" in rendered


def test_telegram_story_chunks_are_safe_and_within_limit():
    markdown = "# Título & prueba\n\n" + ("A < B y texto largo. " * 80)
    chunks = telegram_story_chunks(markdown, limit=90)
    assert all(len(chunk) <= 90 for chunk in chunks)
    assert all(chunk.count("<b>") == chunk.count("</b>") for chunk in chunks)
    plain = html.unescape(re.sub(r"</?b>", "", "".join(chunks)))
    assert plain.replace(" ", "") == (
        "Título & prueba" + ("A < B y texto largo. " * 80)
    ).replace(" ", "")
