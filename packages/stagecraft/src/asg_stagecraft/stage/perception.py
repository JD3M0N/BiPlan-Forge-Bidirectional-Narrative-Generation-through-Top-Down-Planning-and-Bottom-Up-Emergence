"""Who perceives what, on stage.

Pure and deterministic, and the reason a character can be wrong about the story: an actor is
only ever told what its own memory holds, and this module decides what reaches that memory.
It is the drama counterpart of the escape room's partial beliefs, where an agent's policy reads
its beliefs and never the world state.

The rule is small enough to state in full: a public turn is perceived by everyone on stage, a
whisper only by its speaker and the characters it is addressed to, and a thought only by whoever
thought it. Under ActorMemory.SHARED the first case widens to the whole cast, which is the
control arm that isolates what the memory model itself contributes.
"""

from __future__ import annotations

from ..formats import ActorMemory
from .schemas import ActorTurnDraft, StageTurn


def witnesses(
    turn: ActorTurnDraft,
    *,
    actor_id: str,
    on_stage: list[str],
    whole_cast: list[str],
    memory: ActorMemory,
) -> list[str]:
    """List every character who perceives one turn, the speaker included.

    ``on_stage`` and ``whole_cast`` keep their given order, so the result is stable.
    """
    if turn.visibility == "whisper":
        addressed = [item for item in on_stage if item in set(turn.addressed_to)]
        return _ordered(actor_id, addressed, on_stage)
    audience = whole_cast if memory is ActorMemory.SHARED else on_stage
    return _ordered(actor_id, audience, audience)


def perceives(character_id: str, turn: StageTurn) -> bool:
    """Say whether one character perceived a turn that already happened."""
    return character_id in set(turn.witnesses)


def visible_text(turn: StageTurn, character_id: str, names: dict[str, str]) -> str:
    """Render one turn as a given character perceived it, hiding what they could not know.

    A character reads its own thought and never anyone else's, which is what makes a scene
    transcript differ between two actors who both stood through it.
    """
    if turn.kind == "world":
        return f"({turn.action})" if turn.action else ""
    speaker = names.get(turn.actor_id, turn.actor_id)
    pieces: list[str] = []
    if turn.actor_id == character_id and turn.thought:
        pieces.append(f"[pienso: {turn.thought}]")
    if turn.action:
        pieces.append(f"({speaker} {turn.action})")
    if turn.speech:
        target = ""
        if turn.visibility == "whisper":
            addressed = ", ".join(names.get(item, item) for item in turn.addressed_to)
            target = f" (en voz baja a {addressed})" if addressed else " (en voz baja)"
        pieces.append(f"{speaker}{target}: {turn.speech}")
    return " ".join(pieces)


def _ordered(actor_id: str, chosen: list[str], order: list[str]) -> list[str]:
    """Return the speaker plus the chosen characters, deduplicated in the given order."""
    selected = set(chosen) | {actor_id}
    result = [item for item in order if item in selected]
    if actor_id not in result:
        result.insert(0, actor_id)
    return result
