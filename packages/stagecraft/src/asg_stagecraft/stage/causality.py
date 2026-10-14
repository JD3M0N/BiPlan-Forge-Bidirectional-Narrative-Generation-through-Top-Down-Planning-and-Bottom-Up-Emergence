"""Evidence boundaries shared by direction, memory and adaptive revisions."""

from __future__ import annotations

import re

from .perception import stage_direction
from .schemas import EvidenceSource, StageTurn

# Where a director shortens a quote. Every piece around one must still be literal, in order.
_ELLIPSIS = re.compile(r"\s*(?:\[\s*(?:\.\.\.|\u2026)\s*\]|\.\.\.|\u2026)\s*")
# A shortened quote must still say something: fewer words than this prove nothing.
_MIN_QUOTED_WORDS = 3


def _quoted_in(excerpt: str, text: str) -> bool:
    """Say whether an excerpt is literal in a text, whole or as ordered pieces around ellipses."""
    if excerpt in text:
        return True
    pieces = [piece.strip(" ,;:") for piece in _ELLIPSIS.split(excerpt)]
    pieces = [piece for piece in pieces if piece]
    if len(pieces) < 2 or sum(len(piece.split()) for piece in pieces) < _MIN_QUOTED_WORDS:
        return False
    position = 0
    for piece in pieces:
        found = text.find(piece, position)
        if found < 0:
            return False
        position = found + len(piece)
    return True


def _readings(turn: StageTurn, channel: str, names: dict[str, str] | None) -> list[str]:
    """Return a channel's text as logged and as the director's transcript shows it.

    The transcript puts the performer's name before an action and lowers its capital (see
    stage_direction), so a director quoting what it read wrote "Aleth se desliza" for a turn
    logged as "Se desliza": in the 7.12.2 sky-island run 20 of 42 shown clauses were cited
    that way and refused, and five of ten beats were forced.
    """
    text = getattr(turn, channel)
    readings = [text]
    speaker = (names or {}).get(turn.actor_id, "")
    if text and speaker and turn.kind == "actor":
        if channel == "action":
            readings.append(stage_direction(speaker, text, names or {}))
        elif channel == "speech":
            readings.append(f"{speaker}: {text}")
    return readings


def cited_source(
    source: EvidenceSource,
    turns: dict[str, StageTurn],
    *,
    private: str = "",
    names: dict[str, str] | None = None,
) -> StageTurn | None:
    """Validate the literal source, never infer the truth of a character's assertion."""
    turn = turns.get(source.turn_id)
    if turn is None or not source.excerpt.strip():
        return None
    if source.channel == "thought" and turn.actor_id != private:
        return None
    if not any(_quoted_in(source.excerpt, text) for text in _readings(turn, source.channel, names)):
        return None
    return turn


def observable_sources(
    sources: list[EvidenceSource],
    ids: list[str],
    turns: dict[str, StageTurn],
    names: dict[str, str] | None = None,
) -> list[tuple[EvidenceSource, StageTurn]]:
    """Read exact citations, accepting old ID-only citations only when unambiguous."""
    if not sources:
        for key in ids:
            turn = turns.get(key)
            if turn is None:
                continue
            channels = [name for name in ("action", "speech") if getattr(turn, name)]
            if len(channels) == 1:
                sources = [
                    *sources,
                    EvidenceSource(
                        turn_id=key, channel=channels[0], excerpt=getattr(turn, channels[0])
                    ),
                ]
    return [
        (source, turn)
        for source in sources
        if (turn := cited_source(source, turns, names=names)) is not None
    ]
