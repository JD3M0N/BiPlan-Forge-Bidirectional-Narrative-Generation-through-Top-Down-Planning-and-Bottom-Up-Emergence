import html
import re

from asg_telegram.prompts import METRIC_EXPLANATIONS, telegram_story_chunks


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
