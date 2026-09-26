"""Whether one proposed turn may join the performance log.

Every ValueError message raised here stays in English ASCII on purpose, exactly as in graph.py,
promises.py and script/validation.py: the engine reinjects it verbatim into the actor's retry
prompt. It is part of the contract with the model, not text for a reader.

Normalize more, reject less, for the same reason the script validator does: a form with exactly
one possible correction is corrected instead of spending an attempt. What is rejected is what
would corrupt the log - an empty turn, internal identifiers leaking into the fiction, a turn
that swallows several beats at once, and repetition.

Repetition gets its own rule because it is the failure mode the drama-agent literature reports
most: actors restate their last line in new words until a scene stops moving. The threshold is
deliberately stricter than the 0.4 edit-distance gate IBSEN used and still found insufficient.
"""

from __future__ import annotations

import re

from .memory import tokens
from .schemas import ActorTurnDraft

# A candidate is a repeat when it overlaps this much with one of the speaker's own recent turns.
REPETITION_THRESHOLD = 0.75
# How many of the speaker's own previous turns a candidate is compared against.
REPETITION_WINDOW = 3

_WHITESPACE = re.compile(r"\s+")
_LEADING_DASHES = "—–-"
# Internal identifiers look like event-3 or chapter_2; a reader must never see one.
_INTERNAL_ID = re.compile(r"\b(?:event|chapter|scene|promise|beat)[-_]\d+\b", re.IGNORECASE)


def normalize_turn(
    turn: ActorTurnDraft, *, on_stage: list[str], actor_name: str = ""
) -> ActorTurnDraft:
    """Clean cosmetic drift and fix the forms that have exactly one correct reading."""
    # Quotes and a dialogue dash both get stripped, and a model that adds one often adds the
    # other, so the pair is peeled until neither is left rather than once each.
    speech = _clean(turn.speech)
    for _ in range(3):
        stripped = _unquote(speech).lstrip(_LEADING_DASHES).strip()
        if stripped == speech:
            break
        speech = stripped
    action = _strip_own_name(_unwrap(_clean(turn.action)), actor_name)
    thought = _unwrap(_clean(turn.thought))
    # An actor cannot address someone who is not in the scene; dropping them is the only
    # correction that keeps the turn, and the cast is the script's, not the actor's, to change.
    addressed = [item for item in dict.fromkeys(turn.addressed_to) if item in set(on_stage)]
    visibility = turn.visibility
    # A whisper with nobody to whisper to is a public line that mislabelled itself.
    if visibility == "whisper" and not addressed:
        visibility = "public"
    return turn.model_copy(
        update={
            "speech": speech,
            "action": action,
            "thought": thought,
            "addressed_to": addressed,
            "visibility": visibility,
            "tactic": _clean(turn.tactic),
        }
    )


def validate_turn(
    turn: ActorTurnDraft,
    *,
    previous_speech: list[str],
    beat_count: int,
) -> None:
    """Accept one normalized turn, or explain in English why the actor must try again."""
    if not turn.speech and not turn.action:
        raise ValueError(
            "the turn is empty: say something, or do something an audience can see, or both"
        )
    offenders = sorted(
        {
            match.group(0)
            for field in (turn.speech, turn.action)
            for match in _INTERNAL_ID.finditer(field)
        }
    )
    if offenders:
        raise ValueError(
            f"the turn exposes internal identifiers ({', '.join(offenders)}); a character never "
            "names a plan event or a chapter, only what is happening to them"
        )
    if turn.speech.lstrip().startswith("#") or turn.action.lstrip().startswith("#"):
        raise ValueError("the turn contains a Markdown heading; write only what is said and done")
    if beat_count > 1:
        raise ValueError(
            "the turn carries more than one beat at once; play one move and let the others answer"
        )
    repeated = _closest_repeat(turn.speech, previous_speech)
    if repeated is not None:
        raise ValueError(
            f"this repeats what you already said ({repeated!r}); change tactic instead of "
            "restating your position in new words"
        )


def similarity(left: str, right: str) -> float:
    """Score lexical overlap between two lines, as the repetition rule measures it."""
    first, second = set(tokens(left)), set(tokens(right))
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def echo_of(line: str, candidates: list[str]) -> float:
    """Return how closely one line echoes the nearest of a set, 0 when the set is empty."""
    return max((similarity(line, item) for item in candidates), default=0.0)


def _closest_repeat(speech: str, previous: list[str]) -> str | None:
    """Return the recent line a candidate repeats, or None when it says something new."""
    if not speech:
        return None
    for earlier in reversed(previous[-REPETITION_WINDOW:]):
        if similarity(speech, earlier) >= REPETITION_THRESHOLD:
            return earlier[:80]
    return None


def _strip_own_name(action: str, actor_name: str) -> str:
    """Drop the character's own name from the front of their action.

    Every renderer already prefixes the action with whoever performed it, so an actor that
    writes "Mara limpia sus lentes" comes out as "(Mara Mara limpia sus lentes)". Models do this
    often, and the fix has exactly one reading, so it is corrected instead of rejected.
    """
    if not actor_name or not action:
        return action
    # Models drop either the full name or just the first one, so both are tried, longest first.
    candidates = [actor_name]
    first = actor_name.split()[0] if actor_name.split() else ""
    if len(first) >= 3 and first != actor_name:
        candidates.append(first)
    lowered = action.casefold()
    for candidate in candidates:
        prefix = candidate.casefold()
        if not lowered.startswith(prefix):
            continue
        # Only strip a whole word: "Anda hacia la puerta" must survive a character called Ana.
        rest = action[len(candidate) :]
        if rest[:1].isalpha():
            continue
        remainder = rest.lstrip(" ,:")
        if remainder:
            return remainder
    return action


def strip_internal_ids(value: str) -> str:
    """Remove plan identifiers from text on its way to an actor.

    The scene objective comes from the script, which the Playwright wrote while looking at the
    plan, so it can carry an event ID. An actor that reads one can repeat it, and then the
    reader sees it. Stripping here is cheaper and more certain than asking two agents not to.
    """
    return _WHITESPACE.sub(" ", _INTERNAL_ID.sub("", value)).strip(" ,;:.-")


def _clean(value: str) -> str:
    """Collapse whitespace and strip a leading Markdown marker."""
    return _WHITESPACE.sub(" ", value).strip()


def _unwrap(value: str) -> str:
    """Strip one layer of wrapping parentheses or brackets the model added on its own."""
    stripped = value.strip()
    for opening, closing in (("(", ")"), ("[", "]")):
        if stripped.startswith(opening) and stripped.endswith(closing):
            return stripped[1:-1].strip()
    return stripped


def _unquote(value: str) -> str:
    """Strip wrapping quotation marks around a spoken line."""
    stripped = value.strip()
    for opening, closing in (('"', '"'), ("«", "»"), ("“", "”"), ("'", "'")):
        if len(stripped) > 1 and stripped.startswith(opening) and stripped.endswith(closing):
            return stripped[1:-1].strip()
    return stripped
