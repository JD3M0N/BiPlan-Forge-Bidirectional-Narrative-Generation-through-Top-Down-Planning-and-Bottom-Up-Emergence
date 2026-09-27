"""A deterministic narrator for when the model one cannot be run.

Part of the contract rather than a patch: a performance that was played must not be lost
because the narration call failed. It also earns its keep as a measurement, because it is the
floor the model narrator is compared against - the same log, rendered with no interpretation at
all.

It invents nothing. Speech becomes dialogue under the Spanish dash convention, actions become
sentences, thoughts become reported interiority, and that is all.
"""

from __future__ import annotations

from .perception import stage_direction
from .schemas import StageTurn


def narrate(turns: list[StageTurn], names: dict[str, str]) -> str:
    """Render performed turns as plain prose paragraphs, adding nothing."""
    paragraphs: list[str] = []
    for turn in turns:
        if turn.kind == "world":
            paragraphs.append(_sentence(turn.action))
            continue
        speaker = names.get(turn.actor_id, turn.actor_id)
        if turn.action:
            paragraphs.append(_sentence(stage_direction(speaker, turn.action, names)))
        if turn.speech:
            aside = ""
            if turn.visibility == "whisper":
                addressed = ", ".join(names.get(item, item) for item in turn.addressed_to)
                aside = f" en voz baja a {addressed}" if addressed else " en voz baja"
            paragraphs.append(f"—{_strip_final_stop(turn.speech)} —dijo {speaker}{aside}.")
        if turn.thought:
            paragraphs.append(_sentence(f"{speaker} penso que {_lower_first(turn.thought)}"))
    return "\n\n".join(paragraphs)


def _sentence(text: str) -> str:
    """Capitalize and close one rendered sentence."""
    stripped = text.strip()
    if not stripped:
        return ""
    stripped = stripped[0].upper() + stripped[1:]
    return stripped if stripped[-1] in ".!?…" else f"{stripped}."


def _strip_final_stop(text: str) -> str:
    """Drop a trailing period so the dialogue dash carries the punctuation."""
    stripped = text.strip()
    return stripped[:-1] if stripped.endswith(".") else stripped


def _lower_first(text: str) -> str:
    """Lowercase the first letter so reported thought reads as one sentence."""
    stripped = text.strip()
    return stripped[0].lower() + stripped[1:] if stripped else stripped
