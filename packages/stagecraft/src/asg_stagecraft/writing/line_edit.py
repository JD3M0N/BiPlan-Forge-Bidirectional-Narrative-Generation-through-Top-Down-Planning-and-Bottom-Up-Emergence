"""The line editor: rewrite only the paragraphs the code flags, keep an edit only if it helps.

Added in 7.17. Chakrabarty, Laban and Wu (2025) found that professional writers agree on what
goes wrong in model prose - an awkward word, a sentence shape, telling, a cliche - and that
editing the span they point at beats rewriting the whole text. Here the code points:
asg_core.craft flags each paragraph with what a reader stumbles on, the editor sees only those
paragraphs, and an edit ships only when the same detectors find less in it and it is no longer,
names nobody new and puts no new word in anyone's mouth. The Writer's whole-chapter rewrite
lengthened 66 of 69 chapters in 6.2 and merged paragraphs in 7.10; an edit that fails these
checks leaves its paragraph as it was.

Every figure lives here, like the rest of the pipeline's measurements: the editor only ever
reads the observation in words.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from asg_core.craft import (
    ATMOSPHERIC_OPENING,
    EMOTION_TAG,
    GERUND_TAG,
    LONG_PARAGRAPH,
    LONG_WORDS,
    NAMED_TAG,
    REPEATED_NAME,
    REPORTED_CHAIN,
    SIMILE_CHAIN,
    STOCK_PHRASE,
    STOCK_PHRASES,
    carries_quotes,
    opens_with_dash,
    paragraph_flags,
)
from pydantic import BaseModel, ConfigDict, Field

# A paragraph that repeats this many words in a row of a style example copied it.
EXAMPLE_ECHO = "example_echo"
EXAMPLE_RUN = 5
# An edit may grow a paragraph by this share at most, or by one word when it is very short.
MAX_GROWTH = 1.1

# What the editor is told about each observation. The words, never the figure behind them.
OBSERVATIONS = {
    EMOTION_TAG: (
        "the dialogue tag explains how the line was said: cut the explanation and keep a "
        "gesture or nothing"
    ),
    GERUND_TAG: (
        "the dialogue tag trails a gerund clause: cut it, or make the gesture a sentence of its own"
    ),
    NAMED_TAG: (
        "the tag names the speaker: drop the tag, or the name, where the exchange already "
        "makes clear who speaks; where it does not, leave the paragraph out"
    ),
    REPEATED_NAME: (
        "a character is named in two sentences in a row: let the verb or a pronoun carry the "
        "second one"
    ),
    LONG_WORDS: "the vocabulary is heavier than a general reader expects: use everyday words",
    REPORTED_CHAIN: (
        "the paragraph lists one thing after another that the characters said, like the "
        "minutes of a meeting: keep what matters as what someone does or wants, and merge the "
        "rest into one sentence or cut it"
    ),
    LONG_PARAGRAPH: (
        "the paragraph is one long block: split it with a blank line where the attention shifts"
    ),
    STOCK_PHRASE: (
        "it uses a worn phrase: replace it with a concrete detail of this scene, or cut it"
    ),
    SIMILE_CHAIN: "comparisons pile up: keep one at most",
    ATMOSPHERIC_OPENING: (
        "the chapter opens on the air or the weather: open on a character doing something, "
        "and keep the detail only if it matters"
    ),
    EXAMPLE_ECHO: "it copies the style example word for word: say it in this scene's own words",
}

_BLOCKS = re.compile(r"\n[ \t]*\n+")
_DASHES = re.compile(r"[—–]")
_WORDS = re.compile(r"[^\W\d_]+")
# A capitalized word that does not open a sentence: where a name the edit invented would show.
_INNER_CAPITAL = re.compile(
    r"(?<=[^\W\d_,;:] )[A-ZÁÉÍÓÚÑ][^\W\d_]+|(?<=[,;:] )[A-ZÁÉÍÓÚÑ][^\W\d_]+"
)
_IMPERFECT = re.compile(r"\b[^\W\d_]+(?:aba|ía)\b", re.IGNORECASE)
_PRESENT_TAG = re.compile(
    r"[—–]\s*(?:dice|pregunta|responde|contesta|murmura|susurra|grita|exclama|añade|"
    r"replica|ordena|insiste)\b",
    re.IGNORECASE,
)
_PARAGRAPH_ID = re.compile(r"^P(\d+)$")


class LineEdit(BaseModel):
    """One flagged paragraph, rewritten."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="The id of the paragraph this replaces, exactly as given (P1...).")
    text: str = Field(
        min_length=1,
        description=(
            "The paragraph rewritten in the fiction's language, with its accents and dialogue "
            "dashes. It may be split in two with a blank line, never made longer."
        ),
    )


class LineEdits(BaseModel):
    """The paragraphs the editor could improve; the rest stay as they are."""

    model_config = ConfigDict(extra="forbid")
    edits: list[LineEdit] = Field(default_factory=list)


@dataclass
class ChapterEdit:
    """One chapter after the editor: its body, and what was flagged, kept and turned down."""

    body: str
    flagged: dict[str, list[str]] = field(default_factory=dict)
    originals: dict[str, str] = field(default_factory=dict)
    accepted: dict[str, str] = field(default_factory=dict)
    rejected: dict[str, str] = field(default_factory=dict)

    def as_record(self) -> dict:
        """The edit as stored in line_edits/chapter-NNN.json."""
        return {
            "flagged": self.flagged,
            "originals": self.originals,
            "accepted": self.accepted,
            "rejected": self.rejected,
        }


def chapter_blocks(body: str) -> list[str]:
    """Split a chapter body into its paragraphs, as written."""
    return [block.strip() for block in _BLOCKS.split(body.strip()) if block.strip()]


def block_flags(
    block: str, names: list[str], *, opening: bool = False, examples: tuple[str, ...] = ()
) -> tuple[str, ...]:
    """Name the observations of one paragraph, the copied style example included."""
    codes = paragraph_flags(block, names, opening=opening)
    if examples and _echoes(block, examples):
        codes = (*codes, EXAMPLE_ECHO)
    return codes


def edit_request(blocks: list[str], flags: dict[int, tuple[str, ...]]) -> list[dict]:
    """Build what the editor reads: each flagged paragraph, its observations and its context."""
    request = []
    for index, codes in sorted(flags.items()):
        observations = [OBSERVATIONS[code] for code in codes]
        worn = [phrase for phrase in STOCK_PHRASES if phrase in blocks[index].casefold()]
        if worn:
            observations = [*observations, f"the worn phrases are: {', '.join(worn)}"]
        request.append(
            {
                "id": f"P{index + 1}",
                "text": blocks[index],
                "observations": observations,
                "before": blocks[index - 1] if index else "",
            }
        )
    return request


def check_edit(
    original: str,
    replacement: str,
    *,
    names: list[str],
    known_names: set[str],
    opening: bool = False,
    examples: tuple[str, ...] = (),
) -> str:
    """Say why a replacement may not ship, or return an empty string when it may."""
    text = replacement.strip()
    if not text or text.startswith("#"):
        return "empty or a heading"
    length = _word_count(original)
    if _word_count(text) > max(length + 1, MAX_GROWTH * length):
        return "longer than the paragraph it replaces"
    before = set(block_flags(original, names, opening=opening, examples=examples))
    after: set[str] = set()
    for index, part in enumerate(chapter_blocks(text)):
        after |= set(block_flags(part, names, opening=opening and index == 0, examples=examples))
    if not after < before:
        return "the observations are not reduced"
    invented = _names_outside(text, original, known_names)
    if invented:
        return f"names someone new ({', '.join(invented)})"
    if _dialogue_lines(text) > _dialogue_lines(original) or (
        carries_quotes(text) and not carries_quotes(original)
    ):
        return "adds a line of dialogue"
    said = _folded_words(" ".join(_spoken(text))) - _folded_words(original)
    if said:
        return f"puts new words in a character's mouth ({', '.join(sorted(said)[:3])})"
    if len(_IMPERFECT.findall(text)) > len(_IMPERFECT.findall(original)) + 1 or len(
        _PRESENT_TAG.findall(text)
    ) > len(_PRESENT_TAG.findall(original)):
        return "changes the tense"
    return ""


def edit_chapter(
    body: str,
    names: list[str],
    known_names: set[str],
    call: Callable[[list[dict]], LineEdits],
    *,
    examples: tuple[str, ...] = (),
) -> ChapterEdit:
    """Edit the flagged paragraphs of one chapter, keeping each edit only if it passes."""
    blocks = chapter_blocks(body)
    flags = {
        index: codes
        for index, block in enumerate(blocks)
        if (codes := block_flags(block, names, opening=index == 0, examples=examples))
    }
    if not flags:
        return ChapterEdit(body=body)
    edits = call(edit_request(blocks, flags))
    result = ChapterEdit(
        body=body,
        flagged={f"P{index + 1}": list(codes) for index, codes in flags.items()},
        originals={f"P{index + 1}": blocks[index] for index in flags},
    )
    replaced: dict[int, str] = {}
    for edit in edits.edits:
        match = _PARAGRAPH_ID.match(edit.id.strip())
        index = int(match.group(1)) - 1 if match else -1
        if index not in flags or index in replaced:
            result.rejected[edit.id] = "not a flagged paragraph"
            continue
        reason = check_edit(
            blocks[index],
            edit.text,
            names=names,
            known_names=known_names,
            opening=index == 0,
            examples=examples,
        )
        if reason:
            result.rejected[edit.id] = reason
            continue
        replaced[index] = "\n\n".join(chapter_blocks(edit.text))
        result.accepted[edit.id] = replaced[index]
    result.body = "\n\n".join(replaced.get(index, block) for index, block in enumerate(blocks))
    return result


def _word_count(text: str) -> int:
    """Count the words of a text the way the length rule does."""
    return len(text.split())


def _folded_words(text: str) -> set[str]:
    """Return the distinct words of a text, case folded."""
    return {word.casefold() for word in _WORDS.findall(text)}


def _names_outside(text: str, original: str, known: set[str]) -> list[str]:
    """Return the capitalized words of an edit that neither the paragraph nor the cast has."""
    present = set(_WORDS.findall(original)) | known
    return sorted({word for word in _INNER_CAPITAL.findall(text) if word not in present})


def _dialogue_lines(text: str) -> int:
    """Count the paragraphs of a text that open on a dialogue dash."""
    return sum(opens_with_dash(block) for block in chapter_blocks(text))


def _spoken(text: str) -> list[str]:
    """Return the spoken parts of every dialogue paragraph: what lies between dashes."""
    spoken = []
    for block in chapter_blocks(text):
        if opens_with_dash(block):
            spoken.extend(_DASHES.split(block.lstrip())[1::2])
    return spoken


def _echoes(block: str, examples: tuple[str, ...]) -> bool:
    """Say whether a paragraph repeats EXAMPLE_RUN words in a row of a style example."""
    words = [word.casefold() for word in _WORDS.findall(block)]
    runs = {tuple(words[i : i + EXAMPLE_RUN]) for i in range(len(words) - EXAMPLE_RUN + 1)}
    for example in examples:
        sample = [word.casefold() for word in _WORDS.findall(example)]
        for i in range(len(sample) - EXAMPLE_RUN + 1):
            if tuple(sample[i : i + EXAMPLE_RUN]) in runs:
                return True
    return False
