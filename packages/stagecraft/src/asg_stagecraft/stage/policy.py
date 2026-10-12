"""Who moves next, and when the director is asked whether a beat has landed.

Pure and deterministic, and deliberately dull: the interesting decisions belong to the actors
and the director, so turn order must never become a source of variation between two runs of the
same material.

The rules, in order: whoever the director named, then whoever was just spoken to and has not
answered, then whoever has been silent longest. Nobody speaks twice in a row while someone else
could speak, which is what stops two agents from settling into a duet with a third on stage.
"""

from __future__ import annotations

from .schemas import StageTurn

# How often the director is asked whether the beat has landed. Every turn would double the cost
# of a scene; every fifth lets a scene drift past its point.
CHECK_EVERY = 3


def next_actor(
    *,
    on_stage: list[str],
    turns: list[StageTurn],
    requested: str = "",
) -> str:
    """Name the character who moves next in this scene."""
    if not on_stage:
        raise ValueError("a scene cannot run without a cast")
    # A world event carries a placeholder actor, so it must not count as anyone having moved.
    moved = [turn for turn in turns if turn.kind == "actor"]
    last = moved[-1].actor_id if moved else ""
    candidates = [item for item in on_stage if item != last] or list(on_stage)
    if requested in set(candidates):
        return requested
    answered = _addressed_and_silent(moved, candidates)
    if answered:
        return answered
    return min(candidates, key=lambda item: (_last_spoke(moved, item), on_stage.index(item)))


def should_check(turns_in_beat: int, *, check_every: int = CHECK_EVERY) -> bool:
    """Say whether the director should be asked about the beat after this many turns."""
    return turns_in_beat > 0 and turns_in_beat % check_every == 0


def must_force(turns_in_beat: int, *, turns_per_beat: int) -> bool:
    """Say whether the beat has used its whole budget and must be closed."""
    return turns_in_beat >= turns_per_beat


def _addressed_and_silent(turns: list[StageTurn], candidates: list[str]) -> str:
    """Name whoever the last turn spoke to and who has not answered since."""
    if not turns:
        return ""
    target = [item for item in turns[-1].addressed_to if item in set(candidates)]
    return target[0] if target else ""


def _last_spoke(turns: list[StageTurn], character_id: str) -> int:
    """Return the index of a character's last turn, or -1 when they have not moved yet."""
    for index in range(len(turns) - 1, -1, -1):
        if turns[index].actor_id == character_id:
            return index
    return -1


# How many of the beat's last actor turns must show two characters trading the same moves before
# the director is asked to turn the scene, instead of waiting for its next scheduled check.
DEADLOCK_WINDOW = 4


def is_deadlocked(turns: list[StageTurn], *, window: int = DEADLOCK_WINDOW) -> bool:
    """Say whether two characters are trading the same moves, each repeating their own tactic.

    Found in the 7.10 navigators run: "plead" against "command" three times each, ten turns of
    the same argument before the beat cap forced it. Repetition checks only compare an actor
    with itself, and these lines were worded differently each time; the tactics were not.
    """
    moved = [turn for turn in turns if turn.kind == "actor"][-window:]
    if len(moved) < window:
        return False
    actors = [turn.actor_id for turn in moved]
    if len(set(actors)) != 2 or any(
        left == right for left, right in zip(actors, actors[1:], strict=False)
    ):
        return False
    return all(
        moved[index].tactic and moved[index].tactic == moved[index + 2].tactic
        for index in range(window - 2)
    )
