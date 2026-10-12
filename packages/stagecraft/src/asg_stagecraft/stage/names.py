"""Resolve a character a person named to the character the run actually cast.

A person types a name - "Ana", "ana vela", "ANA" with or without an accent - and the cast was
minted by a model, so the id is never what they typed and the name may carry a surname they did
not write. The rule is the
one actors already live by when they address each other on stage (validation._addressees),
applied to the whole cast: an exact full name or id wins; failing that, a single word of three
letters or more that names one character; anything ambiguous or unknown resolves to nobody,
never to a guess.
"""

from __future__ import annotations

from ..planning.skeleton_match import normalize

# The shortest word that may identify a character on its own; "el" or "de" never should.
MIN_NAME_WORD = 3


def resolve_character(requested: str, names: dict[str, str]) -> str:
    """Return the id of the one character a typed name designates, or an empty string."""
    wanted = normalize(requested)
    if not wanted:
        return ""
    exact = {
        character_id
        for character_id, name in names.items()
        if wanted in {normalize(character_id), normalize(name)}
    }
    if exact:
        return next(iter(exact)) if len(exact) == 1 else ""
    words = {word for word in wanted.split() if len(word) >= MIN_NAME_WORD}
    matches = {
        character_id for character_id, name in names.items() if words & set(normalize(name).split())
    }
    return next(iter(matches)) if len(matches) == 1 else ""


# Words that cannot stand alone as what a character is called.
_TITLES = frozenset(
    "lord lady sir don dona doña senor señor senora señora doctor doctora dr. dra. capitan "
    "capitán capitana padre madre hermano hermana fray sor tio tío tia tía abuela abuelo".split()
)


class ShortNames:
    """Hand out a character's full name once, then the name prose would use after (7.12).

    The fallback and the narrator's log named every character in full on every line, and the
    7.10 stories read that way: about twice as many names as model-narrated chapters.
    """

    def __init__(self, names: dict[str, str]) -> None:
        """Precompute short names, keeping the full one where two characters would collide."""
        self.full = names
        short = {key: short_name(value) for key, value in names.items()}
        taken = list(short.values())
        self.short = {
            key: value if taken.count(value) == 1 else names[key] for key, value in short.items()
        }
        self.seen: set[str] = set()

    def name(self, character_id: str) -> str:
        """The full name on first mention, the short one afterwards."""
        if character_id not in self.full:
            return character_id
        if character_id in self.seen:
            return self.short[character_id]
        self.seen.add(character_id)
        return self.full[character_id]


def short_name(full_name: str) -> str:
    """The first name, or title and name when the first word is a title."""
    words = full_name.split()
    if len(words) > 1 and words[0].lower() in _TITLES:
        return " ".join(words[:2])
    return words[0] if words else full_name
