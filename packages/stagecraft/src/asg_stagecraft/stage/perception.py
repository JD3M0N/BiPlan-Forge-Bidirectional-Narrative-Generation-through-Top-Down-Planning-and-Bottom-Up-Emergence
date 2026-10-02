"""Who perceives what, on stage.

Pure and deterministic, and the reason a character can be wrong about the story: an actor is
only ever told what its own memory holds, and this module decides what reaches that memory.
It is the drama counterpart of partial beliefs in agent simulations, where a policy reads what
the agent believes and never the world state.

The rule is small enough to state in full: a public turn is perceived by everyone on stage, a
whisper only by its speaker and the characters it is addressed to, and a thought only by whoever
thought it. Under ActorMemory.SHARED the first case widens to the whole cast, which is the
control arm that isolates what the memory model itself contributes.

An object move, when the inventory is on, is perceived on the same terms with one addition and
one exception: whoever the object left or reached always perceives it, because a thing changing
hands is felt by both hands, and concealing one is perceived by nobody but its holder. The
witness list itself is computed in stage/inventory.py, which owns where each object is; what
lives here is how such a move reads to one character.
"""

from __future__ import annotations

from ..formats import ActorMemory
from .schemas import ActorTurnDraft, ItemAction, StageTurn


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
        return ordered_witnesses(actor_id, addressed, on_stage)
    audience = whole_cast if memory is ActorMemory.SHARED else on_stage
    return ordered_witnesses(actor_id, audience, audience)


def perceives(character_id: str, turn: StageTurn) -> bool:
    """Say whether one character perceived a turn that already happened."""
    return character_id in set(turn.witnesses)


def stage_direction(speaker: str, action: str, names: dict[str, str]) -> str:
    """Join a performer's name and their action into one stage direction.

    Actors are told to leave their own name out, so an action often arrives capitalized as a
    sentence of its own, and after the name it read "Mara Vela Pasa una pagina" in every 7.1
    transcript. The capital is dropped unless the action opens with someone's name.
    """
    proper = {word.strip(",.;:") for name in names.values() for word in name.split()}
    first = action.split()[0].strip(",.;:") if action.split() else ""
    if action[:1].isupper() and first not in proper:
        action = action[0].lower() + action[1:]
    return f"{speaker} {action}"


def item_line(action: ItemAction, names: dict[str, str], *, concealed_from: bool = False) -> str:
    """Render one object move as a stage direction, in the fiction's own language.

    Deliberately plain and derived, never authored: the actor already wrote what it does in its
    action, and this line is the arbiter's record of what actually changed, so a reader, the
    director and the narrator all see the same sentence.
    """
    who = names.get(action.target_id, action.target_id)
    from_who = names.get(action.from_id, action.from_id)
    item = f"«{action.item_name}»"
    if action.verb == "give":
        return f"[entrega {item} a {who}]" if who else f"[entrega {item}]"
    if action.verb == "take":
        return f"[toma {item} de {from_who}]" if from_who else f"[toma {item}]"
    if action.verb == "drop":
        return f"[deja {item}]"
    if action.verb == "hide":
        return f"[esconde {item}, sin que nadie lo vea]" if concealed_from else f"[esconde {item}]"
    if action.verb == "show":
        return f"[muestra {item} a {who}]" if who else f"[muestra {item}]"
    if action.verb == "use":
        return f"[usa {item} con {who}]" if who else f"[usa {item}]"
    return ""


def perceives_item(character_id: str, turn: StageTurn) -> bool:
    """Say whether one character perceived the object move a turn carried, if it carried one."""
    return bool(turn.item_action) and character_id in set(turn.item_action.witnesses)


def visible_text(turn: StageTurn, character_id: str, names: dict[str, str]) -> str:
    """Render one turn as a given character perceived it, hiding what they could not know.

    A character reads its own thought and never anyone else's, which is what makes a scene
    transcript differ between two actors who both stood through it. An object move is held to
    the same standard: a concealed one appears only to its holder, and a whispered hand-over
    only to the two hands and whoever was whispered to.
    """
    if turn.kind == "world":
        return f"({turn.action})" if turn.action else ""
    speaker = names.get(turn.actor_id, turn.actor_id)
    pieces: list[str] = []
    if turn.actor_id == character_id and turn.thought:
        pieces.append(f"[pienso: {turn.thought}]")
    if turn.action:
        pieces.append(f"({stage_direction(speaker, turn.action, names)})")
    if perceives_item(character_id, turn):
        assert turn.item_action is not None
        line = item_line(turn.item_action, names, concealed_from=turn.item_action.verb == "hide")
        if line:
            pieces.append(line)
    if turn.speech:
        target = ""
        if turn.visibility == "whisper":
            addressed = ", ".join(names.get(item, item) for item in turn.addressed_to)
            target = f" (en voz baja a {addressed})" if addressed else " (en voz baja)"
        pieces.append(f"{speaker}{target}: {turn.speech}")
    return " ".join(pieces)


def ordered_witnesses(actor_id: str, chosen: list[str], order: list[str]) -> list[str]:
    """Return the speaker plus the chosen characters, deduplicated in the given order."""
    selected = set(chosen) | {actor_id}
    # dict.fromkeys so a caller may append the parties of an object move to the order it passes
    # without having to check whether they were already standing there.
    result = [item for item in dict.fromkeys(order) if item in selected]
    if actor_id not in result:
        result.insert(0, actor_id)
    return result
