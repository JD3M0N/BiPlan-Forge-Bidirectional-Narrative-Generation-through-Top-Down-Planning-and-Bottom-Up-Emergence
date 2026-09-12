import html
import re

import pytest
from asg_telegram.contract import ProfileOption
from asg_telegram.prompts import (
    METRIC_EXPLANATIONS,
    build_guided_prompt,
    guided_question,
    telegram_story_chunks,
    validate_guided_value,
)

PROFILES = (
    ProfileOption("essential", "Esencial", ("essential", "esencial")),
    ProfileOption("developed", "Desarrollada", ("developed", "desarrollada")),
    ProfileOption("expansive", "Expansiva", ("expansive", "expansiva")),
)


def guided_values():
    return {
        "language": "español",
        "genre": "fantasía",
        "protagonist": "una cartógrafa",
        "conflict": "las estrellas desaparecen",
        "setting": "una estación orbital",
        "tone": "melancólico",
        "narrative_profile": "developed",
        "constraints": "ninguna",
    }


@pytest.mark.parametrize(
    ("value", "match"),
    [
        ("corta", "Esencial, Desarrollada, Expansiva"),
        ("mil", "Esencial, Desarrollada, Expansiva"),
        ("gigantesca", "Esencial, Desarrollada, Expansiva"),
        ("", None),
    ],
    ids=["unrecognized-word", "unrecognized-number", "unrecognized-label", "empty-answer"],
)
def test_invalid_profile_answers_are_rejected(value, match):
    """Unrecognized answers list the available labels; an empty answer gets its own message."""
    with pytest.raises(ValueError, match=match or ".+"):
        validate_guided_value("narrative_profile", value, PROFILES)


@pytest.mark.parametrize(
    ("answer", "canonical"),
    [
        ("Esencial", "essential"),
        ("Desarrollada", "developed"),
        ("Expansiva", "expansive"),
        ("Automático", "automatic"),
    ],
)
def test_all_guided_profile_paths_are_supported(answer, canonical):
    assert validate_guided_value("narrative_profile", answer, PROFILES) == canonical
    values = guided_values()
    values["narrative_profile"] = canonical
    prompt = build_guided_prompt(values, PROFILES)
    if canonical == "automatic":
        assert "Perfil narrativo:" not in prompt
    else:
        assert "Perfil narrativo:" in prompt
    assert not any(token in prompt for token in (" palabras", " capítulos"))
    if canonical == "developed":
        assert prompt == (
            "Escribe una historia en español. Perfil narrativo: Desarrollada. "
            "Género: fantasía. Protagonista: una cartógrafa. Conflicto principal: "
            "las estrellas desaparecen. Ambientación: una estación orbital. "
            "Tono: melancólico. Restricciones: Sin restricciones adicionales."
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
        explanation.name and explanation.description and explanation.low and explanation.high
        for explanation in METRIC_EXPLANATIONS.values()
    )


def test_telegram_story_formats_headings_and_escapes_html():
    markdown = (
        "# La Cartografía del Silencio\n\n### I. Planteamiento\n\nElena observó A < B & C > D."
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
    assert plain.replace(" ", "") == ("Título & prueba" + ("A < B y texto largo. " * 80)).replace(
        " ", ""
    )


def test_profile_question_names_the_profiles_the_generator_offers():
    question = guided_question(6, PROFILES)
    assert "Esencial, Desarrollada, Expansiva" in question
    assert "Automático" in question
