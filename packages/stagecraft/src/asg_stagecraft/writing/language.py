"""Tell whether a short reader-facing text is written in the language the story asked for.

The plan is written in English on purpose and everything a reader sees is meant to be in the
fiction's language, but the boundary leaks: the 7.13 navigators run printed "Arrival and
Discovery" as a chapter title of a Spanish story. This module only detects the leak, with
function words, so it is deterministic and needs no model. Fixing it is the localizer's job.

Only Spanish and English are told apart; for any other language nothing is ever flagged, so
an unsupported language costs no call and changes nothing.
"""

from __future__ import annotations

import re

# Words that carry grammar rather than content, so a few of them identify a language even in
# a three-word title. Words both languages share ("a", "no") are left out of both lists.
_FUNCTION_WORDS = {
    "en": frozenset(
        "the and of to in with for from on at by his her their is are was were its an into "
        "who that this through after before beyond under over".split()
    ),
    "es": frozenset(
        "el la los las de del y en que un una unos unas con por para su sus al se es lo entre "
        "sin bajo tras hacia sobre desde cuando como".split()
    ),
}
_LANGUAGE_CODES = {
    "spanish": "es",
    "español": "es",
    "espanol": "es",
    "castellano": "es",
    "es": "es",
    "english": "en",
    "inglés": "en",
    "ingles": "en",
    "en": "en",
}
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def language_code(language: str) -> str:
    """Return the code this module knows a language by, or '' when it cannot judge it."""
    return _LANGUAGE_CODES.get(language.strip().lower(), "")


def is_foreign(text: str, language: str) -> bool:
    """Say whether a text reads as the other supported language rather than the asked one.

    A text is foreign when it carries at least one function word of the other language and
    more of them than of its own. A text with none of either (a name, a single noun) is never
    flagged: there is nothing to translate with confidence.
    """
    own = language_code(language)
    if not own:
        return False
    other = "en" if own == "es" else "es"
    words = [word.lower() for word in _WORD.findall(text)]
    foreign = sum(word in _FUNCTION_WORDS[other] for word in words)
    native = sum(word in _FUNCTION_WORDS[own] for word in words)
    return foreign >= 1 and foreign > native


# The language a whole prompt is written in needs more evidence than a title: at least this
# many function words of one language, and this many times those of the other.
_MIN_PROMPT_HITS = 8
_PROMPT_MARGIN = 3
_LANGUAGE_NAMES = {"es": "Spanish", "en": "English"}


def prompt_language(text: str) -> str:
    """Name the language a long text is plainly written in, or '' when it is not plain.

    Found in the 7.15 navigators run: the analyst read a Spanish brief that says "Idioma
    espanol" and returned language English, and the whole story came out in English.
    """
    words = [word.lower() for word in _WORD.findall(text)]
    counts = {
        code: sum(word in _FUNCTION_WORDS[code] for word in words) for code in _FUNCTION_WORDS
    }
    best, other = sorted(counts, key=counts.get, reverse=True)
    if counts[best] >= _MIN_PROMPT_HITS and counts[best] >= _PROMPT_MARGIN * counts[other]:
        return _LANGUAGE_NAMES[best]
    return ""
