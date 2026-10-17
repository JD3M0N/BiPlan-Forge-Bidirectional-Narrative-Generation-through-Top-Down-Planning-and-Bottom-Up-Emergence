"""Deterministic prose craft measurements over generated story Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass

DIALOGUE_DASHES = "\u2014\u2013"
QUOTE_MARKS = "\u00ab\u00bb\u201c\u201d\u201e\u0022"
SENTENCE_TERMINATORS = ".!?\u2026"
RATIO_DIGITS = 4
AVERAGE_DIGITS = 2
ABBREVIATIONS = frozenset(
    {
        "art",
        "cap",
        "dr",
        "dra",
        "ej",
        "etc",
        "fig",
        "num",
        "p",
        "pp",
        "sr",
        "sra",
        "srta",
        "vs",
    }
)

# Deliberately not reusing markdown_to_speech_text: it collapses blank lines and
# drops list markers, destroying the paragraph structure measured here.
_CODE_FENCE = re.compile(r"(?ms)^[ \t]{0,3}(?:```|~~~).*?(?:^[ \t]{0,3}(?:```|~~~)[ \t]*$|\Z)")
_BLOCK_SPLIT = re.compile(r"\n[ \t]*\n+")
_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}(?:\s|$)")
_THEMATIC_BREAK = re.compile(r"^[ \t]{0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
_WORD = re.compile(r"\w")
_SENTENCE_BREAK = re.compile(
    r"[" + re.escape(SENTENCE_TERMINATORS) + r"]+[\"'\u00bb\u201d\u2019)\]]*(?=\s|$)"
)
_LAST_TOKEN = re.compile(r"([^\s.]+)$")


@dataclass(frozen=True)
class CraftMetrics:
    """Prose craft figures observed in one story or chapter body."""

    paragraphs: int
    sentences: int
    words: int
    dash_paragraphs: int
    quoted_paragraphs: int
    dialogue_paragraphs: int
    dialogue_ratio: float
    words_per_sentence: float
    words_per_paragraph: float


def _normalize(text: str) -> str:
    """Unify line endings, spaces and ellipsis before any measurement."""
    unified = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    return unified.replace("...", "\u2026")


def _clean_inline(block: str) -> str:
    """Drop Markdown decoration from a prose block, keeping dialogue marks."""
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", block)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"(?m)^[ \t]{0,3}>[ \t]?", "", text)
    return re.sub(r"\s+", " ", text).strip()


def prose_paragraphs(markdown: str) -> list[str]:
    """Return the clean prose blocks of a story, without headings or code."""
    text = _CODE_FENCE.sub("\n", _normalize(markdown))
    paragraphs = []
    for block in _BLOCK_SPLIT.split(text):
        stripped = block.strip()
        if not stripped or _HEADING.match(stripped) or _THEMATIC_BREAK.match(stripped):
            continue
        if not _WORD.search(stripped):
            continue
        cleaned = _clean_inline(stripped)
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs


def _closes_sentence(text: str, match: re.Match[str]) -> bool:
    """Decide whether a terminator match really closes a sentence."""
    marks = match.group()
    if marks[0] != "." or len(marks) > 1:
        return True
    before = text[: match.start()]
    if before[-1:].isdigit() and text[match.end() :].lstrip()[:1].isdigit():
        return False
    token = _LAST_TOKEN.search(before)
    if token is None:
        return True
    word = token.group(1).lower()
    if word in ABBREVIATIONS:
        return False
    return not (len(word) == 1 and word.isalpha())


def split_sentences(paragraph: str) -> list[str]:
    """Split one prose paragraph into sentences under Spanish punctuation."""
    text = _normalize(paragraph).strip()
    if not _WORD.search(text):
        return []
    sentences = []
    start = 0
    for match in _SENTENCE_BREAK.finditer(text):
        if not _closes_sentence(text, match):
            continue
        piece = text[start : match.end()].strip()
        if piece:
            sentences.append(piece)
        start = match.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def opens_with_dash(paragraph: str) -> bool:
    """Report whether a paragraph opens with a Spanish dialogue dash."""
    stripped = paragraph.lstrip()
    return bool(stripped) and stripped[0] in DIALOGUE_DASHES


def carries_quotes(paragraph: str) -> bool:
    """Report whether a paragraph carries quotation marks anywhere."""
    return any(mark in paragraph for mark in QUOTE_MARKS)


def craft_metrics(markdown: str) -> CraftMetrics:
    """Measure dialogue presence, sentence length and paragraph length in story Markdown."""
    paragraphs = prose_paragraphs(markdown)
    if not paragraphs:
        return CraftMetrics(0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0)
    dashes = [paragraph for paragraph in paragraphs if opens_with_dash(paragraph)]
    quoted = [paragraph for paragraph in paragraphs if carries_quotes(paragraph)]
    dialogue = [
        paragraph
        for paragraph in paragraphs
        if opens_with_dash(paragraph) or carries_quotes(paragraph)
    ]
    words = sum(len(paragraph.split()) for paragraph in paragraphs)
    sentences = sum(len(split_sentences(paragraph)) for paragraph in paragraphs)
    return CraftMetrics(
        paragraphs=len(paragraphs),
        sentences=sentences,
        words=words,
        dash_paragraphs=len(dashes),
        quoted_paragraphs=len(quoted),
        dialogue_paragraphs=len(dialogue),
        dialogue_ratio=round(len(dialogue) / len(paragraphs), RATIO_DIGITS),
        words_per_sentence=round(words / sentences, AVERAGE_DIGITS) if sentences else 0.0,
        words_per_paragraph=round(words / len(paragraphs), AVERAGE_DIGITS),
    )


# A dialogue line whose tag goes on to explain the feeling: "—... —dijo, con una mezcla de...".
_EMOTION_TAG = re.compile(
    r"[" + DIALOGUE_DASHES + r"][^" + DIALOGUE_DASHES + r"\n]+[" + DIALOGUE_DASHES + r"]"
    r"[^.\n]*?\bcon\s+(?:una|un)\s",
    re.IGNORECASE,
)
# Comparisons the reader notices: "como si...", "como un...", "como una...".
_SIMILE = re.compile(r"\bcomo\s+(?:si|una?)\b", re.IGNORECASE)


# What a reported line is narrated with: the speech verbs, in the preterite and as a gerund,
# with an object pronoun or without. In 7.16 the narrator chained them into paragraphs that read
# like minutes ("ordenó..., preguntando..., sugiriendo..."): 32 in 20261017-184641, against 0
# to 1 in every narration before it and 0.3 per 1,000 words in the Top-Down corpus.
_SPEECH_VERBS = (
    ("ordenó", "ordenando"),
    ("exigió", "exigiendo"),
    ("pidió", "pidiendo"),
    ("advirtió", "advirtiendo"),
    ("sugirió", "sugiriendo"),
    ("insistió", "insistiendo"),
    ("preguntó", "preguntando"),
    ("prometió", "prometiendo"),
    ("aseguró", "asegurando"),
    ("afirmó", "afirmando"),
    ("propuso", "proponiendo"),
    ("instó", "instando"),
    ("informó", "informando"),
    ("explicó", "explicando"),
    ("suplicó", "suplicando"),
    ("reclamó", "reclamando"),
    ("rogó", "rogando"),
    ("mandó", "mandando"),
    ("anunció", "anunciando"),
    ("declaró", "declarando"),
)


def _with_pronoun(gerund: str) -> str:
    """Return the accented stem a gerund takes before an attached pronoun (pidiendo-le)."""
    if gerund.endswith("iendo"):
        return gerund[: -len("iendo")] + "iéndo"
    return gerund[: -len("ando")] + "ándo"


REPORTED_SPEECH = re.compile(
    r"\b(?:"
    + "|".join(
        alternative
        for preterite, gerund in _SPEECH_VERBS
        for alternative in (
            preterite,
            gerund,
            _with_pronoun(gerund) + "(?:le|les|lo|la|los|las|se)",
        )
    )
    + r")\b",
    re.IGNORECASE,
)

# The observations a line editor works from (7.17). Each is measured on one paragraph, so an
# editor can be handed only the paragraphs that carry one, and the code can tell whether the
# replacement still does. Calibrated on 2026-10-17 over the paragraphs of 20 words or more of
# the 6.x Top-Down corpus (5,718), the 7.10 narratives the readers rejected (323) and the
# October simulated narrations (1,439).
EMOTION_TAG = "emotion_tag"
GERUND_TAG = "gerund_tag"
NAMED_TAG = "named_tag"
REPEATED_NAME = "repeated_name"
LONG_WORDS = "long_words"
REPORTED_CHAIN = "reported_chain"
LONG_PARAGRAPH = "long_paragraph"
STOCK_PHRASE = "stock_phrase"
SIMILE_CHAIN = "simile_chain"
ATMOSPHERIC_OPENING = "atmospheric_opening"

LONG_WORD_LETTERS = 9
# Reached by 16 % of the 6.x paragraphs, 9 % of the 7.10 ones and 7 % of the simulated ones;
# their medians are 0.15, 0.13 and 0.08.
LONG_WORD_SHARE = 0.22
# Below this many words a share says nothing.
MIN_SHARE_WORDS = 20
LONG_PARAGRAPH_WORDS = 100
# Each found in the stories of at least 16 of the 68 distinct Spanish prompts of the corpus
# ("un paso al frente" in 39), plus the ones the readers' runs repeated within one story.
STOCK_PHRASES = (
    "un paso al frente",
    "con la mirada fija",
    "los ojos fijos en",
    "con paso firme",
    "sintiendo cómo",
    "un golpe seco",
    "con voz firme",
    "el zumbido constante",
    "la voz quebrada",
    "sintiendo el peso",
    "bajo el peso de",
    "con precisión milimétrica",
    "un chasquido seco",
    "un chasquido metálico",
    "un movimiento seco",
    "exhaló un suspiro",
    "a pocos centímetros",
    "con pulso firme",
    "la tensión acumulada",
    "cuestión de segundos",
    "se tornaron blancos",
    "de oreja a oreja",
    "silencio sepulcral",
    "un escalofrío recorrió",
)
# "No era una nota, sino una frecuencia de corte": the construction the slop literature finds
# several times more often in model prose than in human prose.
_NOT_X_BUT_Y = re.compile(r"\bno (?:era|es|fue) (?:solo |sólo )?[^,.;:]{1,40}, sino\b", re.I)
# A chapter that opens on the weather or the air: 12 of the 14 chapters of the 7.10 narratives.
_SENSORY_OPENING = re.compile(
    r"^(?:el|la|los|las)\s+(?:aire|viento|brisa|silencio|calor|frío|eco|zumbido|rugido|"
    r"murmullo|crujido|chirrido|estruendo|timbre|sonido|olor|aroma|hedor|luz|sol|niebla|"
    r"bruma|lluvia|tormenta|nieve|humo|vapor|polvo|penumbra|sombra|sombras|oscuridad|noche|"
    r"amanecer|atardecer)\b",
    re.IGNORECASE,
)
_TAG = re.compile(
    r"^[" + DIALOGUE_DASHES + r"][^" + DIALOGUE_DASHES + r"\n]+"
    r"[" + DIALOGUE_DASHES + r"]\s*([^" + DIALOGUE_DASHES + r"\n]*)"
)
_GERUND = re.compile(
    r"\b[^\W\d_]+(?:ando|iendo|yendo)\b|\b[^\W\d_]+(?:ándo|iéndo)(?:le|les|lo|la|los|las|se)\b",
    re.IGNORECASE,
)
_LETTERS = re.compile(r"[^\W\d_]+")


def speech_tag(paragraph: str) -> str:
    """Return what follows the spoken line of a dialogue paragraph when it opens a tag."""
    match = _TAG.match(paragraph.lstrip())
    tag = match.group(1).strip() if match else ""
    return tag if tag[:1].islower() else ""


def stock_phrases(text: str) -> int:
    """Count the stock phrases and the 'no X, sino Y' constructions of a text."""
    folded = text.casefold()
    return sum(folded.count(phrase) for phrase in STOCK_PHRASES) + len(_NOT_X_BUT_Y.findall(text))


def long_word_share(text: str) -> float:
    """Return the share of a text's words of LONG_WORD_LETTERS letters or more."""
    words = _LETTERS.findall(text)
    return sum(len(word) >= LONG_WORD_LETTERS for word in words) / len(words) if words else 0.0


def _name_patterns(names: list[str] | tuple[str, ...]) -> list[re.Pattern[str]]:
    """Compile one whole-word pattern per non-empty character name."""
    return [re.compile(r"\b" + re.escape(name) + r"\b") for name in names if name.strip()]


def _repeats_name(paragraph: str, patterns: list[re.Pattern[str]]) -> bool:
    """Say whether a paragraph names a character in two sentences in a row."""
    previous: set[int] = set()
    for sentence in split_sentences(paragraph):
        current = {index for index, pattern in enumerate(patterns) if pattern.search(sentence)}
        if current & previous:
            return True
        previous = current
    return False


def paragraph_flags(
    paragraph: str, names: list[str] | tuple[str, ...] = (), *, opening: bool = False
) -> tuple[str, ...]:
    """Name the observations one prose paragraph carries, in a fixed order."""
    patterns = _name_patterns(names)
    words = len(paragraph.split())
    flags: list[str] = []
    if opens_with_dash(paragraph):
        tag = speech_tag(paragraph)
        if tag and _EMOTION_TAG.search(paragraph):
            flags.append(EMOTION_TAG)
        if tag and _GERUND.search(tag):
            flags.append(GERUND_TAG)
        if tag and any(pattern.search(tag) for pattern in patterns):
            flags.append(NAMED_TAG)
    else:
        if len(REPORTED_SPEECH.findall(paragraph)) >= 2:
            flags.append(REPORTED_CHAIN)
        if words >= LONG_PARAGRAPH_WORDS:
            flags.append(LONG_PARAGRAPH)
    if _repeats_name(paragraph, patterns):
        flags.append(REPEATED_NAME)
    if words >= MIN_SHARE_WORDS and long_word_share(paragraph) >= LONG_WORD_SHARE:
        flags.append(LONG_WORDS)
    if stock_phrases(paragraph):
        flags.append(STOCK_PHRASE)
    if len(_SIMILE.findall(paragraph)) >= 2:
        flags.append(SIMILE_CHAIN)
    if opening and _SENSORY_OPENING.match(paragraph):
        flags.append(ATMOSPHERIC_OPENING)
    return tuple(flags)


@dataclass(frozen=True)
class ReadabilitySignals:
    """How heavy a prose body reads, in figures no prompt ever receives (7.12).

    Added after readers outside the project called the stories hard to read. Measured on the
    corpus: name_repeat_ratio has a p90 of 0.20 in the 6.x Top-Down chapters and 0.5 to 0.8 in
    the 7.10 fallback narration; tagged_dialogue_ratio reached 0.6 in the 7.10 narrative runs.
    The rest came in 7.17 for the run comparison, which reads them whole; the line editor works
    paragraph by paragraph from paragraph_flags.
    """

    name_repeat_ratio: float
    tagged_dialogue_ratio: float
    similes_per_100_words: float
    speech_tag_ratio: float
    gerund_tag_ratio: float
    long_word_ratio: float
    reported_speech_per_1000_words: float
    stock_phrases_per_1000_words: float
    flagged_paragraph_ratio: float


def readability_signals(
    markdown: str, names: list[str] | tuple[str, ...] = ()
) -> ReadabilitySignals:
    """Measure repeated names, dialogue tags, simile density and the paragraph observations.

    name_repeat_ratio is the share of sentences that name a character already named in the
    sentence before, which is what a reader feels as "the name in every line".
    """
    paragraphs = prose_paragraphs(markdown)
    words = sum(len(paragraph.split()) for paragraph in paragraphs)
    patterns = _name_patterns(names)
    previous: set[int] = set()
    repeats = sentences = 0
    for paragraph in paragraphs:
        for sentence in split_sentences(paragraph):
            sentences += 1
            current = {index for index, pattern in enumerate(patterns) if pattern.search(sentence)}
            repeats += bool(current & previous)
            previous = current
    dialogue = [paragraph for paragraph in paragraphs if opens_with_dash(paragraph)]
    tags = [speech_tag(paragraph) for paragraph in dialogue]
    prose = " ".join(paragraphs)
    narration = " ".join(paragraph for paragraph in paragraphs if not opens_with_dash(paragraph))
    flagged = sum(
        bool(paragraph_flags(paragraph, names, opening=index == 0))
        for index, paragraph in enumerate(paragraphs)
    )
    return ReadabilitySignals(
        name_repeat_ratio=_ratio(repeats, sentences),
        tagged_dialogue_ratio=_ratio(
            sum(bool(_EMOTION_TAG.search(paragraph)) for paragraph in dialogue), len(dialogue)
        ),
        similes_per_100_words=_per(len(_SIMILE.findall(prose)), words, 100),
        speech_tag_ratio=_ratio(sum(bool(tag) for tag in tags), len(dialogue)),
        gerund_tag_ratio=_ratio(
            sum(bool(tag and _GERUND.search(tag)) for tag in tags), len(dialogue)
        ),
        long_word_ratio=round(long_word_share(prose), RATIO_DIGITS),
        reported_speech_per_1000_words=_per(len(REPORTED_SPEECH.findall(narration)), words, 1000),
        stock_phrases_per_1000_words=_per(stock_phrases(prose), words, 1000),
        flagged_paragraph_ratio=_ratio(flagged, len(paragraphs)),
    )


def _ratio(part: int, whole: int) -> float:
    """Return part / whole rounded like every ratio here, 0 when there is no whole."""
    return round(part / whole, RATIO_DIGITS) if whole else 0.0


def _per(count: int, words: int, scale: int) -> float:
    """Return a count per `scale` words rounded like every average here, 0 without words."""
    return round(scale * count / words, AVERAGE_DIGITS) if words else 0.0
