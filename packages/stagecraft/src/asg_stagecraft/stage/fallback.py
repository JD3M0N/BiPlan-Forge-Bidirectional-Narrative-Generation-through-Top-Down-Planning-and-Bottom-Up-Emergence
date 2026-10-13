"""A deterministic narrator for when the model one cannot be run.

Part of the contract rather than a patch: a performance that was played must not be lost
because the narration call failed. It also earns its keep as a measurement, because it is the
floor the model narrator is compared against - the same log, rendered with no interpretation at
all.

It invents nothing. Speech becomes dialogue under the Spanish dash convention, actions become
sentences, thoughts become italic interior lines, an object changing hands becomes the sentence
the arbiter recorded, and that is all.

Since 7.12 it reads like prose rather than a transcript: one paragraph per turn, the full name
only the first time a character appears, the short name after that, no name when the paragraph
already says who acts, and one tense throughout. Its 7.10 output named a character in every
line, about twice as often as model-narrated chapters, and wrote "penso que" before a thought
in the first person.
"""

from __future__ import annotations

from .language import is_foreign
from .names import ShortNames
from .perception import item_line, item_moves, stage_direction
from .schemas import StageTurn


def narrate(turns: list[StageTurn], names: dict[str, str], language: str = "") -> str:
    """Render performed turns as plain prose paragraphs, adding nothing."""
    calls = ShortNames(names)
    paragraphs: list[str] = []
    for turn in turns:
        if turn.kind == "world":
            paragraphs.append(_sentence(turn.action))
            continue
        speaker = calls.name(turn.actor_id)
        sentences: list[str] = []
        if turn.action:
            sentences.append(_sentence(stage_direction(speaker, turn.action, names)))
        for move in item_moves(turn):
            moved = item_line(move, names).strip("[]")
            if moved:
                sentences.append(_sentence(f"{speaker} {moved}"))
        named = bool(sentences)
        if turn.speech:
            tag = "" if named else f" —dice {speaker}"
            if turn.visibility == "whisper":
                addressed = ", ".join(calls.name(item) for item in turn.addressed_to)
                tag = tag or " —dice"
                tag += f" en voz baja a {addressed}" if addressed else " en voz baja"
            sentences.append(_sentence(f"—{_strip_final_stop(turn.speech)}{tag}"))
            named = named or bool(tag)
        thought = turn.thought.strip()
        if thought and not is_foreign(thought, language):
            who = "" if named else f" {speaker}"
            sentences.append(f"*{_strip_final_stop(thought)}*, piensa{who}.")
        paragraph = " ".join(sentence for sentence in sentences if sentence)
        if paragraph:
            paragraphs.append(paragraph)
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
