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


@dataclass(frozen=True)
class ReadabilitySignals:
    """How heavy a prose body reads, in figures no prompt ever receives (7.12).

    Added after readers outside the project called the stories hard to read. Measured on the
    corpus: name_repeat_ratio has a p90 of 0.20 in the 6.x Top-Down chapters and 0.5 to 0.8 in
    the 7.10 fallback narration; tagged_dialogue_ratio reached 0.6 in the 7.10 narrative runs.
    """

    name_repeat_ratio: float
    tagged_dialogue_ratio: float
    similes_per_100_words: float


def readability_signals(
    markdown: str, names: list[str] | tuple[str, ...] = ()
) -> ReadabilitySignals:
    """Measure repeated names, emotion-explaining dialogue tags and simile density.

    name_repeat_ratio is the share of sentences that name a character already named in the
    sentence before, which is what a reader feels as "the name in every line".
    """
    paragraphs = prose_paragraphs(markdown)
    words = sum(len(paragraph.split()) for paragraph in paragraphs)
    patterns = [re.compile(r"\b" + re.escape(name) + r"\b") for name in names if name.strip()]
    previous: set[int] = set()
    repeats = sentences = 0
    for paragraph in paragraphs:
        for sentence in split_sentences(paragraph):
            sentences += 1
            current = {index for index, pattern in enumerate(patterns) if pattern.search(sentence)}
            repeats += bool(current & previous)
            previous = current
    dialogue = [paragraph for paragraph in paragraphs if opens_with_dash(paragraph)]
    tagged = sum(bool(_EMOTION_TAG.search(paragraph)) for paragraph in dialogue)
    return ReadabilitySignals(
        name_repeat_ratio=round(repeats / sentences, RATIO_DIGITS) if sentences else 0.0,
        tagged_dialogue_ratio=round(tagged / len(dialogue), RATIO_DIGITS) if dialogue else 0.0,
        similes_per_100_words=(
            round(100 * len(_SIMILE.findall(" ".join(paragraphs))) / words, AVERAGE_DIGITS)
            if words
            else 0.0
        ),
    )
