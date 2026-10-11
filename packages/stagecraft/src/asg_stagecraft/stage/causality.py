"""Evidence boundaries shared by direction, memory and adaptive revisions."""

from __future__ import annotations

from .schemas import EvidenceSource, StageTurn


def cited_source(
    source: EvidenceSource, turns: dict[str, StageTurn], *, private: str = ""
) -> StageTurn | None:
    """Validate the literal source, never infer the truth of a character's assertion."""
    turn = turns.get(source.turn_id)
    if turn is None or not source.excerpt.strip():
        return None
    if source.channel == "thought" and turn.actor_id != private:
        return None
    if source.excerpt not in getattr(turn, source.channel):
        return None
    return turn


def observable_sources(
    sources: list[EvidenceSource], ids: list[str], turns: dict[str, StageTurn]
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
        (source, turn) for source in sources if (turn := cited_source(source, turns)) is not None
    ]
