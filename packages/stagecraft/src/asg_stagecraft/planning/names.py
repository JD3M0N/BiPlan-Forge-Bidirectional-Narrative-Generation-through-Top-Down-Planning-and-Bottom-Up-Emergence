"""Choose each character's name in code, from candidates the designer proposes (7.17, TD-7).

"Elena" is in 54 of 170 casts of the corpus, and the 7.12.1 navigators got Rodrigo de Triana and
"San Salvador" for a people the prompt asked to be new, though the prompt forbade both. Names are
priors of each model family (Gemini reaches for "Aris Thorne"), and naming a forbidden word in a
prompt tends to call it up. Flash-Lite ignores the temperature, so the variety has to come from
the code: the designer proposes three names per character with how typical each would be for it,
as Verbalized Sampling asks, and this module keeps the least typical one that is not on a list
the prompt never sees. A run stays reproducible: the choice depends only on its own response.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection

from ..schemas import CharacterProfile, CharactersArtifact

# The stock names of generated fiction, folded to lowercase ASCII. Read from the corpus and from
# the slop literature; never written into a prompt.
STOCK_NAMES = frozenset(
    "elena elara aris thorne lena petrova voss vance vargas tomas mateo marta lucia kael lyra "
    "seraphina silas julian mara".split()
)
_WORDS = re.compile(r"[^\W\d_]+")


def _fold(text: str) -> str:
    """Fold a word to lowercase ASCII, so accents never decide a match."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    return folded.encode("ascii", "ignore").decode()


def _first(name: str) -> str:
    """Return the folded first word of a name."""
    words = _WORDS.findall(name)
    return _fold(words[0]) if words else ""


def _stock(name: str) -> bool:
    """Say whether any word of a name is a stock name."""
    return any(_fold(word) in STOCK_NAMES for word in _WORDS.findall(name))


def choose_names(
    characters: CharactersArtifact, fixed: Collection[str] = ()
) -> tuple[CharactersArtifact, list[dict]]:
    """Keep each character's least typical acceptable candidate, renaming it everywhere.

    A name the author fixed (a brief's cast) is never touched, and a character with no
    acceptable candidate keeps the name it came with. Returns the cast and what was chosen.
    """
    pinned = {_fold(name) for name in fixed} | {_first(name) for name in fixed}
    taken: set[str] = set()
    renames: dict[str, tuple[str, str]] = {}
    choices: list[dict] = []
    for character in characters.characters:
        options = [option for option in character.name_options if option.name.strip()]
        if _fold(character.name) in pinned or _first(character.name) in pinned or not options:
            taken.add(_first(character.name))
            continue
        acceptable = [
            option
            for option in options
            if not _stock(option.name) and _first(option.name) not in taken
        ]
        chosen = (
            min(acceptable, key=lambda option: option.typicality).name.strip()
            if acceptable
            else character.name
        )
        taken.add(_first(chosen))
        choices.append(
            {
                "character_id": character.id,
                "proposed": character.name,
                "options": [option.model_dump(mode="json") for option in options],
                "chosen": chosen,
            }
        )
        if chosen != character.name:
            renames[character.id] = (character.name, chosen)
    return _renamed(characters, renames), choices


def _new_ids(characters: CharactersArtifact, renames: dict[str, tuple[str, str]]) -> dict:
    """Mint a new id from the new name for a renamed character whose id came from the old one.

    An id like elena_vance next to the name Ilse Marvento would hand the old name back to the
    planner, which reads both.
    """
    used = {character.id for character in characters.characters}
    ids: dict[str, str] = {}
    for character_id, (old, new) in renames.items():
        minted = re.sub(r"[^a-z0-9]+", "_", _fold(new)).strip("_")
        if _first(old) in character_id and minted and minted not in used:
            ids[character_id] = minted
            used.add(minted)
    return ids


def _renamed(
    characters: CharactersArtifact, renames: dict[str, tuple[str, str]]
) -> CharactersArtifact:
    """Apply every rename to every name, id and text of the cast, whole names and first names."""
    ids = _new_ids(characters, renames)
    pairs: list[tuple[str, str]] = []
    for old, new in renames.values():
        pairs.append((old, new))
        old_first, new_first = old.split()[0], new.split()[0]
        if old_first != old:
            pairs.append((old_first, new_first))
    patterns = [(re.compile(r"\b" + re.escape(old) + r"\b"), new) for old, new in pairs]

    def rewrite(text: str) -> str:
        """Replace every renamed name in one text, the whole names first."""
        for pattern, new in patterns:
            text = pattern.sub(new, text)
        return text

    def profile(character: CharacterProfile) -> CharacterProfile:
        """Rename one character and every mention of the others in its texts."""
        fields = {
            name: rewrite(value)
            for name, value in character.model_dump().items()
            if isinstance(value, str) and name != "id"
        }
        identity = ids.get(character.id, character.id)
        return character.model_copy(update={**fields, "id": identity, "name_options": []})

    relationships = [
        relationship.model_copy(
            update={
                name: ids.get(value, value) if name.endswith("_id") else rewrite(value)
                for name, value in relationship.model_dump().items()
                if isinstance(value, str)
            }
        )
        for relationship in characters.relationships
    ]
    return characters.model_copy(
        update={
            "characters": [profile(item) for item in characters.characters],
            "relationships": relationships,
        }
    )
