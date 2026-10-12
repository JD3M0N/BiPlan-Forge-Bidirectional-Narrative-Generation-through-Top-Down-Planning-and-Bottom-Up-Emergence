"""A deterministic check that a performed line is in the fiction's language.

The actor's speech, gesture and thought all reach the reader, through the narrator or the
fallback. In the 7.10 runs thoughts came back in English ("mateo is sharp, but he needs my
route") because only speech was tied to the language in the actor's instruction. No model and
no dependency: the share of English function words against Spanish ones is enough to tell a
sentence in one from a sentence in the other, and a short line with a foreign name in it does
not trip it.
"""

from __future__ import annotations

import re

_ENGLISH = frozenset(
    "the and is are was were be been to of that this with for not but you your he she they "
    "them his her its it we our will would should can could have has had do does did if "
    "then than what when where who why how my me i am an at on in by from as or so just".split()
)
_SPANISH = frozenset(
    "el la los las y es son era eran ser estar esta este esto que de del con para por no pero "
    "tu su sus ella ellos lo le les se nos mi me yo un una unos unas al en como si cuando "
    "donde quien porque muy ya hay fue ha han mas sin sobre entre hasta desde".split()
)
_WORD = re.compile(r"[a-zà-ÿ]+")
# Below this many function words a line says too little to judge, and is left alone.
_MIN_SIGNAL = 3


def is_foreign(text: str, language: str) -> bool:
    """Tell whether a line meant to be in Spanish is mostly English.

    Only Spanish fictions are judged: for any other language the check abstains rather than
    guessing, so it can never reject a valid turn.
    """
    if not language.strip().lower().startswith(("spanish", "espa")):
        return False
    words = _WORD.findall(text.lower())
    english = sum(word in _ENGLISH for word in words)
    spanish = sum(word in _SPANISH for word in words)
    if english + spanish < _MIN_SIGNAL:
        return False
    return english > 2 * spanish
