"""Point of view as a strategy: what the narrator is allowed to see in the log.

Focalization is a property of the *discourse*, not of the story, so it belongs here rather than
in the narrator's prompt: the same performance log can be narrated three ways without replaying
a single turn. Each strategy answers two questions - who narrates, and which turns reach them -
and the prompt only ever receives the result.

Adding a point of view means adding a strategy to VOICES. Nothing else changes.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from ..formats import NarrativeVoice
from .schemas import ScenePerformance, StageTurn


@dataclass(frozen=True)
class VoiceStrategy:
    """One point of view: who tells the story and what they are able to tell."""

    voice: NarrativeVoice
    needs_narrator: bool
    visible: Callable[[list[StageTurn], str, str], list[StageTurn]]


def _omniscient(turns: list[StageTurn], narrator: str, focal: str) -> list[StageTurn]:
    """Return everything, thoughts and concealed objects included: this narrator sees all."""
    return list(turns)


def _focalized(turns: list[StageTurn], narrator: str, focal: str) -> list[StageTurn]:
    """Return everything public, keeping only the focal character's inner life.

    An object somebody else put out of sight counts as inner life: the focal character did not
    see it happen, so a narrator bound to them cannot report it.
    """
    return [
        turn
        if turn.actor_id == focal
        else turn.model_copy(update={"thought": "", **_withheld_item(turn, focal)})
        for turn in turns
    ]


def _first_person(turns: list[StageTurn], narrator: str, focal: str) -> list[StageTurn]:
    """Return only what the narrator witnessed, with only the narrator's own thoughts.

    This is where the memory model pays off twice: a first-person chapter can only be written
    from turns its narrator actually perceived, and those are exactly the turns already recorded
    in that character's stream. Objects follow the same boundary, which is the point of pairing
    an inventory with a point of view: a hand-over nobody told this narrator about is not theirs
    to narrate, so the reader learns who holds what only as the narrator does.
    """
    return [
        turn
        if turn.actor_id == narrator
        else turn.model_copy(update={"thought": "", **_withheld_item(turn, narrator)})
        for turn in turns
        if narrator in set(turn.witnesses)
    ]


def _withheld_item(turn: StageTurn, character_id: str) -> dict[str, None]:
    """Drop the object move of a turn whose own object move this character did not perceive."""
    if turn.item_action is None or character_id in set(turn.item_action.witnesses):
        return {}
    return {"item_action": None}


VOICES: dict[NarrativeVoice, VoiceStrategy] = {
    NarrativeVoice.OMNISCIENT: VoiceStrategy(NarrativeVoice.OMNISCIENT, False, _omniscient),
    NarrativeVoice.FOCALIZED: VoiceStrategy(NarrativeVoice.FOCALIZED, False, _focalized),
    NarrativeVoice.FIRST_PERSON: VoiceStrategy(NarrativeVoice.FIRST_PERSON, True, _first_person),
    # Third person limited sees exactly what first person sees; only the grammatical person the
    # narrator is told to write in differs, and that lives in the narrator's clause.
    NarrativeVoice.LIMITED: VoiceStrategy(NarrativeVoice.LIMITED, True, _first_person),
}


def narrator_character(
    voice: NarrativeVoice,
    scenes: list[ScenePerformance],
    *,
    requested: str = "",
    protagonist: str = "",
) -> str:
    """Name the character who narrates, or an empty string when nobody does.

    A character the caller asked for wins, then the declared protagonist; without either, the
    character who took the most turns does, which is the only measure available that does not
    require reading the story.
    """
    if not VOICES[voice].needs_narrator:
        return ""
    if requested:
        return requested
    if protagonist:
        return protagonist
    tally: Counter[str] = Counter()
    for scene in scenes:
        for turn in scene.turns:
            tally[turn.actor_id] += 1
    return min(tally, key=lambda item: (-tally[item], item)) if tally else ""


def focal_character(scene: ScenePerformance) -> str:
    """Name whose inner life a focalized narrator may enter in one scene."""
    tally: Counter[str] = Counter(turn.actor_id for turn in scene.turns)
    return min(tally, key=lambda item: (-tally[item], item)) if tally else ""


def visible_turns(
    voice: NarrativeVoice,
    scene: ScenePerformance,
    *,
    narrator: str = "",
    present: frozenset[str] | None = None,
) -> list[StageTurn]:
    """Return the turns of one scene as the configured point of view is able to see them.

    present is the scene's cast when the caller knows it. A voice told from one character sees
    nothing of a scene that character was not in, whatever the witness lists say: under shared
    memory every public turn lists the whole cast, and the narrator would otherwise report
    scenes they never stood in, mixing the memory ablation into the narration.
    """
    strategy = VOICES[voice]
    if strategy.needs_narrator and present is not None and narrator not in present:
        return []
    return strategy.visible(scene.turns, narrator, focal_character(scene))
