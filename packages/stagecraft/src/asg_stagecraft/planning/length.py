"""The profile a request asks for by its length: words, pages, chapters or plain words for size.

Added in 7.20. Until then only a request for 1,500 words or fewer, or for "una historia corta",
was read by the code; everything longer was a "weak signal" left to the analyst, and the
islands brief, whose notes say "Historia extensa", ran Essential with nobody noticing.

The bands follow what each profile measured on the corpus before 7.20: Essential narratives
came out at 1,400 to 2,000 words, Developed ones at about 2,550. A profile is a structure, not a
budget, so nothing here reaches a prompt: the figures only choose the profile.
"""

from __future__ import annotations

import re

from .profiles import NarrativeProfile, profile_chapter_band

# Requested words up to these choose Essential, then Developed; anything longer is Expansive.
ESSENTIAL_MAX_WORDS = 2000
DEVELOPED_MAX_WORDS = 4000
# A printed page of prose, for requests counted in pages.
WORDS_PER_PAGE = 300

EXPLICIT_PROFILE = re.compile(
    r"\b(?:perfil(?:\s+narrativo)?|narrative\s+profile)\s*[:=-]?\s*"
    r"(esencial|essential|desarrollada|developed|expansiva|expansive)\b",
    re.IGNORECASE,
)
PROFILE_ALIASES = {
    "esencial": NarrativeProfile.ESSENTIAL,
    "essential": NarrativeProfile.ESSENTIAL,
    "desarrollada": NarrativeProfile.DEVELOPED,
    "developed": NarrativeProfile.DEVELOPED,
    "expansiva": NarrativeProfile.EXPANSIVE,
    "expansive": NarrativeProfile.EXPANSIVE,
}

_NOUN = r"(?:historia|cuento|relato|narraci(?:ó|o)n|obra|texto|novela)"
# Size words count only next to a noun for a story: "una larga noche" asks for nothing.
_QUALITATIVE: tuple[tuple[re.Pattern[str], NarrativeProfile], ...] = (
    (
        re.compile(
            rf"\bnovela\s+corta\b|\bnouvelle\b|\bnovell?a\b|\bnovelette\b|\blong\s+story\b"
            rf"|\b{_NOUN}\s+(?:muy\s+|bien\s+)?(?:extens[ao]|larg[ao]|amplia|ampli[ao])\b",
            re.IGNORECASE,
        ),
        NarrativeProfile.EXPANSIVE,
    ),
    (
        re.compile(
            rf"\b{_NOUN}\s+(?:muy\s+)?(?:cort[ao]|breve)\b|\bmicrorrelato\b|\bminicuento\b"
            r"|\bshort\s+story\b|\bflash\s+fiction\b",
            re.IGNORECASE,
        ),
        NarrativeProfile.ESSENTIAL,
    ),
    (
        re.compile(
            rf"\b{_NOUN}\s+(?:de\s+)?(?:extensi(?:ó|o)n|longitud|largo)\s+medi[ao]\b"
            rf"|\b{_NOUN}\s+mediana\b",
            re.IGNORECASE,
        ),
        NarrativeProfile.DEVELOPED,
    ),
)

_UNITS = {
    "un": 1,
    "uno": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "quince": 15,
    "veinte": 20,
    "treinta": 30,
    "cuarenta": 40,
    "cincuenta": 50,
    "sesenta": 60,
    "setenta": 70,
    "ochenta": 80,
    "noventa": 90,
    "cien": 100,
    "ciento": 100,
    "doscientas": 200,
    "doscientos": 200,
    "trescientas": 300,
    "trescientos": 300,
    "cuatrocientas": 400,
    "cuatrocientos": 400,
    "quinientas": 500,
    "quinientos": 500,
    "seiscientas": 600,
    "seiscientos": 600,
    "setecientas": 700,
    "setecientos": 700,
    "ochocientas": 800,
    "ochocientos": 800,
    "novecientas": 900,
    "novecientos": 900,
}
_NUMBER_WORD = "|".join(sorted([*_UNITS, "mil", "y"], key=len, reverse=True))
_AMOUNT = rf"(\d[\d.,]*|(?:(?:{_NUMBER_WORD})\s+)*(?:{_NUMBER_WORD}))"
_WORDS = re.compile(rf"(?<![\w.,]){_AMOUNT}\s*(?:mil\s+)?(?:palabras?|words?)\b", re.IGNORECASE)
_PAGES = re.compile(rf"(?<![\w.,]){_AMOUNT}\s*(?:p(?:á|a)ginas?|pages?)\b", re.IGNORECASE)
_CHAPTERS = re.compile(rf"(?<![\w.,]){_AMOUNT}\s*(?:cap(?:í|i)tulos?|chapters?)\b", re.IGNORECASE)


def requested_profile(prompt: str) -> tuple[NarrativeProfile, str] | None:
    """Return the profile a request's own length asks for, and why, or None when it asks none.

    A named profile wins, then a count of words, pages or chapters, then a word for size next
    to the story it qualifies.
    """
    named = EXPLICIT_PROFILE.search(prompt)
    if named:
        return PROFILE_ALIASES[named.group(1).casefold()], f"nombra el perfil «{named.group(0)}»"
    words = _count(_WORDS, prompt)
    if words:
        return profile_for_words(words), f"pide unas {words} palabras"
    pages = _count(_PAGES, prompt)
    if pages:
        return profile_for_words(pages * WORDS_PER_PAGE), f"pide {pages} páginas"
    chapters = _count(_CHAPTERS, prompt)
    if chapters:
        return profile_for_chapters(chapters), f"pide {chapters} capítulos"
    for pattern, profile in _QUALITATIVE:
        found = pattern.search(prompt)
        if found:
            return profile, f"pide «{found.group(0)}»"
    return None


def profile_for_words(words: int) -> NarrativeProfile:
    """Map a requested word count onto the profile whose measured length holds it."""
    if words <= ESSENTIAL_MAX_WORDS:
        return NarrativeProfile.ESSENTIAL
    if words <= DEVELOPED_MAX_WORDS:
        return NarrativeProfile.DEVELOPED
    return NarrativeProfile.EXPANSIVE


def profile_for_chapters(chapters: int) -> NarrativeProfile:
    """Map a requested chapter count onto the first profile whose band reaches it."""
    for profile in NarrativeProfile:
        if chapters <= profile_chapter_band(profile)[1]:
            return profile
    return NarrativeProfile.EXPANSIVE


def _count(pattern: re.Pattern[str], prompt: str) -> int:
    """Read the last amount the pattern finds, in digits or in Spanish words, or 0."""
    amounts = [_amount(match.group(1), match.group(0)) for match in pattern.finditer(prompt)]
    amounts = [amount for amount in amounts if amount]
    return amounts[-1] if amounts else 0


def _amount(text: str, whole: str) -> int:
    """Turn '2.000', '2000' or 'dos mil quinientas' into a number, or 0."""
    digits = re.sub(r"[.,\s]", "", text)
    if digits.isdigit():
        value = int(digits)
    else:
        value = _spanish_number(text)
    # "3 mil palabras" puts the thousand after the figure.
    if re.search(r"\bmil\s+(?:palabras?|words?)\b", whole, re.IGNORECASE) and value < 1000:
        value *= 1000
    return value


def _spanish_number(text: str) -> int:
    """Read a number written in Spanish words, up to the thousands."""
    total = current = 0
    for word in text.casefold().split():
        if word == "mil":
            total += max(current, 1) * 1000
            current = 0
        elif word in _UNITS:
            current += _UNITS[word]
    return total + current
