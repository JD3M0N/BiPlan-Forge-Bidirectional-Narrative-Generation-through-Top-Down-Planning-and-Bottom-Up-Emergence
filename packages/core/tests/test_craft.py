"""Tests for the prose craft primitives shared by both approaches."""

from asg_core import CraftMetrics, craft_metrics, prose_paragraphs, split_sentences

DASH = "—"
ELLIPSIS = "…"
SCENE = (
    f"{DASH}¿Ocurre algo, Mateo? {DASH}preguntó Julián, "
    f"sin levantar la vista{DASH}. "
    "Llevas media hora mirando el mismo fotograma.\n\n"
    "El proyeccionista guardó silencio. La bobina seguía girando en falso, "
    "y el haz de luz dibujaba un rectángulo vacío sobre la pantalla.\n\n"
    f"{DASH}Nada {DASH}mintió{DASH}. Polvo en la lente."
)


def test_prose_paragraphs_skip_headings_rules_and_code_fences():
    """Keep only the blocks that carry prose, in document order."""
    markdown = (
        "# La sombra del faro\n\n"
        "## Primer capitulo\n\n"
        "El faro llevaba semanas apagado.\n\n"
        "---\n\n"
        "```\nno es prosa\n```\n\n"
        "Nadie quiso decirlo en voz alta.\n"
    )
    assert prose_paragraphs(markdown) == [
        "El faro llevaba semanas apagado.",
        "Nadie quiso decirlo en voz alta.",
    ]


def test_a_markdown_list_item_is_not_a_dialogue_paragraph():
    """Treat a leading hyphen as list syntax, never as a dialogue dash."""
    metrics = craft_metrics("- un item de lista\n\n- otro item\n")
    assert metrics.paragraphs == 2
    assert metrics.dash_paragraphs == 0
    assert metrics.dialogue_ratio == 0.0


def test_dash_openers_and_quotes_are_counted_apart_and_united():
    """Separate the strong dash signal from the weak quotation signal."""
    markdown = (
        f"{DASH}Vengo por el cuadro.\n\n"
        'El restaurador lo llamo "la copia perfecta" sin mirarle a la cara.\n\n'
        f"{DASH}Entonces «sabes» quien lo hizo.\n\n"
        "La sala olia a barniz fresco.\n"
    )
    metrics = craft_metrics(markdown)
    assert metrics.paragraphs == 4
    assert metrics.dash_paragraphs == 2
    assert metrics.quoted_paragraphs == 2
    assert metrics.dialogue_paragraphs == 3
    assert metrics.dialogue_ratio == 0.75


def test_an_inner_dash_does_not_add_a_dialogue_paragraph():
    """Ignore the narrator aside inside a paragraph that does not open a line."""
    metrics = craft_metrics(f"La bobina {DASH}ya inservible{DASH} giraba en falso.\n")
    assert metrics.paragraphs == 1
    assert metrics.dash_paragraphs == 0
    assert metrics.dialogue_paragraphs == 0


def test_sentences_split_on_terminators_and_survive_spanish_openers():
    """Close a sentence on the question mark and never on its opening sign."""
    assert split_sentences("¿Quien apago el faro? Nadie respondio.") == [
        "¿Quien apago el faro?",
        "Nadie respondio.",
    ]
    assert split_sentences("¡Basta! Se acabo.") == ["¡Basta!", "Se acabo."]


def test_three_dots_and_the_ellipsis_character_end_one_sentence():
    """Normalize three dots so an ellipsis never invents two sentences."""
    assert split_sentences("No lo se... Quiza manana.") == [
        f"No lo se{ELLIPSIS}",
        "Quiza manana.",
    ]
    assert split_sentences(f"No lo se{ELLIPSIS} Quiza manana.") == [
        f"No lo se{ELLIPSIS}",
        "Quiza manana.",
    ]


def test_decimal_numbers_and_abbreviations_do_not_end_a_sentence():
    """Hold the sentence together across decimals, abbreviations and initials."""
    assert split_sentences("El Sr. Vidal pago 1.500 euros por el lote.") == [
        "El Sr. Vidal pago 1.500 euros por el lote."
    ]
    assert split_sentences("Firmo M. Silva el acta.") == ["Firmo M. Silva el acta."]


def test_a_paragraph_without_a_terminator_still_counts_one_sentence():
    """Never report words without sentences, which would void the average."""
    metrics = craft_metrics("Una frase sin punto final\n")
    assert metrics.sentences == 1
    assert metrics.words_per_sentence == 5.0


def test_empty_heading_only_and_whitespace_text_yield_zeroes():
    """Return zeroed figures instead of failing on text without prose."""
    zeroed = CraftMetrics(0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0)
    assert craft_metrics("") == zeroed
    assert craft_metrics("# Solo un titulo\n\n## Y un capitulo\n") == zeroed
    assert craft_metrics("   \n\n  \n") == zeroed
    assert split_sentences("   ") == []


def test_crlf_and_non_breaking_spaces_match_the_normalized_input():
    """Measure a Windows-edited story exactly like its normalized twin."""
    unix = "Primer parrafo del faro.\n\nSegundo parrafo del faro.\n"
    windows = unix.replace(chr(10), chr(13) + chr(10)).replace(chr(32), chr(160), 1)
    assert craft_metrics(windows) == craft_metrics(unix)


def test_craft_metrics_are_deterministic_and_rounded():
    """Report stable figures with a fixed number of decimals."""
    first = craft_metrics(SCENE)
    assert first == craft_metrics(SCENE)
    assert first.dialogue_ratio == round(first.dialogue_ratio, 4)
    assert first.words_per_sentence == round(first.words_per_sentence, 2)
    assert first.words_per_paragraph == round(first.words_per_paragraph, 2)


def test_a_real_dialogue_scene_reports_the_expected_figures():
    """Pin every figure of a dramatized scene in the corpus style."""
    assert craft_metrics(SCENE) == CraftMetrics(
        paragraphs=3,
        sentences=7,
        words=44,
        dash_paragraphs=2,
        quoted_paragraphs=0,
        dialogue_paragraphs=2,
        dialogue_ratio=0.6667,
        words_per_sentence=6.29,
        words_per_paragraph=14.67,
    )


def test_a_narrator_aside_splits_the_line_it_interrupts():
    """Document the known bias: a dialogue aside adds one short sentence."""
    line = f"{DASH}Nada {DASH}mintio{DASH}. Polvo en la lente."
    assert split_sentences(line) == [f"{DASH}Nada {DASH}mintio{DASH}.", "Polvo en la lente."]
