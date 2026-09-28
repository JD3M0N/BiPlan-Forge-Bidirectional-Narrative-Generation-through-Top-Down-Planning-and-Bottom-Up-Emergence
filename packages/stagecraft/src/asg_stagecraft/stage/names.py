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
