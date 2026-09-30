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

from ..planning.skeleton_match import normalize
from .memory import tokens
from .schemas import ActorTurnDraft

# A candidate is a repeat when it overlaps this much with one of the speaker's own earlier lines.
# Speech is compared against everything the speaker has said in the play: a near-verbatim line is
# a repeat however long ago it was said, and 7.1 had one said again a whole scene later.
REPETITION_THRESHOLD = 0.75
# How many of the speaker's own previous gestures a new action is compared against.
REPETITION_WINDOW = 3
# A word of a name shorter than this says too little to pick one character out of a cast.
_MIN_NAME_WORD = 3
# A gesture is replayed when the new action contains this much of an earlier one. Containment,
# not overlap: the real repeats kept the whole gesture and tacked a clause onto it.
ACTION_CONTAINMENT = 0.8
# A thought that says this much of what the speech already says is not subtext, only an echo.
THOUGHT_ECHO = 0.5
# The longest line that still reads as a turn rather than a speech. It lives here and never in a
# prompt, like every other figure the stage measures.
MAX_SPEECH_WORDS = 45

_WHITESPACE = re.compile(r"\s+")
_LEADING_DASHES = "—–-"
# Internal identifiers look like event-3 or chapter_2; a reader must never see one.
_INTERNAL_ID = re.compile(r"\b(?:event|chapter|scene|promise|beat)[-_]\d+\b", re.IGNORECASE)
# First-person markers in a stage direction. Deliberately conservative: it catches "me
# arrodillo" and "la palma de mi mano" and lets a bare first-person verb through, because
# guessing Spanish conjugation from one word would reject honest third-person directions.
_FIRST_PERSON = re.compile(r"^(?:me|yo)\b|\b(?:mi|mis|conmigo)\b", re.IGNORECASE)


class TurnIssue(ValueError):
    """A rejected turn, carrying the code the audit files it under.

    Still a ValueError, so the message is what the actor's retry prompt receives verbatim.
    """

    def __init__(self, code: str, message: str) -> None:
        """Store the rejection code next to the English message."""
        super().__init__(message)
        self.code = code


def normalize_turn(
    turn: ActorTurnDraft,
    *,
    on_stage: list[str],
    actor_name: str = "",
    names: dict[str, str] | None = None,
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
    # A thought that restates the line is not subtext. It has one correct fix - there is nothing
    # left to record - so it is emptied rather than bounced back to the actor.
    if thought and speech and similarity(thought, speech) >= THOUGHT_ECHO:
        thought = ""
    # An actor cannot address someone who is not in the scene; dropping them is the only
    # correction that keeps the turn, and the cast is the script's, not the actor's, to change.
    addressed = _addressees(turn.addressed_to, on_stage, names or {})
    visibility = turn.visibility
    # A whisper without a resolved recipient is rejected; making it public leaks a secret.
    return turn.model_copy(
        update={
            "speech": speech,
            "action": action,
            "thought": thought,
            "addressed_to": addressed,
            "visibility": visibility,
        }
    )


def validate_turn(
    turn: ActorTurnDraft,
    *,
    previous_speech: list[str],
    previous_actions: list[str] | None = None,
) -> None:
    """Accept one normalized turn, or raise a TurnIssue saying in English what to fix."""
    if turn.visibility == "whisper" and not turn.addressed_to:
        raise TurnIssue("INVALID_WHISPER", "a whisper needs one unambiguous addressee on stage")
    if re.search(
        r"`|\b(?:as an ai|i am checking the import paths|superset/models)\b|\b\w+\.py\b",
        f"{turn.speech} {turn.action}",
        re.IGNORECASE,
    ):
        raise TurnIssue(
            "OUT_OF_FICTION", "the turn refers to code or an assistant task outside the fiction"
        )
    if not turn.speech and not turn.action:
        raise TurnIssue(
            "EMPTY_TURN",
            "the turn is empty: say something, or do something an audience can see, or both",
        )
    offenders = sorted(
        {
            match.group(0)
            for field in (turn.speech, turn.action)
            for match in _INTERNAL_ID.finditer(field)
        }
    )
    if offenders:
        raise TurnIssue(
            "INTERNAL_IDENTIFIERS",
            f"the turn exposes internal identifiers ({', '.join(offenders)}); a character never "
            "names a plan event or a chapter, only what is happening to them",
        )
    if turn.speech.lstrip().startswith("#") or turn.action.lstrip().startswith("#"):
        raise TurnIssue(
            "INTERNAL_IDENTIFIERS",
            "the turn contains a Markdown heading; write only what is said and done",
        )
    if len(turn.speech.split()) > MAX_SPEECH_WORDS:
        raise TurnIssue(
            "LONG_SPEECH",
            "the line is a speech, not a turn: say the one thing that matters now and let the "
            "others answer",
        )
    if turn.action and _FIRST_PERSON.search(turn.action):
        raise TurnIssue(
            "FIRST_PERSON_ACTION",
            "the action is written in the first person; write it as a stage direction, in the "
            "third person and without your own name",
        )
    repeated = _closest_repeat(turn.speech, previous_speech)
    if repeated is not None:
        raise TurnIssue(
            "REPEATED_LINE",
            f"this repeats what you already said ({repeated!r}); change tactic instead of "
            "restating your position in new words",
        )
    if _replays_gesture(turn.action, previous_actions or []):
        raise TurnIssue(
            "REPEATED_ACTION",
            "you already made this gesture; do something new, or say something without it",
        )


def containment(earlier: str, later: str) -> float:
    """Return how much of an earlier line survives inside a later one, from 0 to 1."""
    first, second = set(tokens(earlier)), set(tokens(later))
    if not first:
        return 0.0
    return len(first & second) / len(first)


def is_first_person_action(action: str) -> bool:
    """Say whether a stage direction carries the conservative first-person markers."""
    return bool(action and _FIRST_PERSON.search(action))


def _replays_gesture(action: str, previous: list[str]) -> bool:
    """Say whether a new action replays one of the actor's own recent gestures."""
    if not action:
        return False
    return any(
        containment(earlier, action) >= ACTION_CONTAINMENT
        for earlier in previous[-REPETITION_WINDOW:]
        if earlier
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
    """Return the earlier line a candidate repeats, or None when it says something new."""
    if not speech:
        return None
    for earlier in reversed(previous):
        if similarity(speech, earlier) >= REPETITION_THRESHOLD:
            return earlier[:80]
    return None


def _addressees(requested: list[str], on_stage: list[str], names: dict[str, str]) -> list[str]:
    """Map what an actor wrote as recipients onto the IDs of the characters on stage.

    Actors are shown names and never IDs, so a recipient arrives as "Mara Vela", "Mara" or
    "Vela". Each one is resolved when it can only mean one character present - by ID, full name
    or a single word of the name - and dropped otherwise. In 7.1 the schema asked for IDs the
    actor had never seen, and 79 turns of 80 reached the log addressed to nobody.
    """
    keys: dict[str, set[str]] = {}
    for character_id in on_stage:
        name = normalize(names.get(character_id, ""))
        candidates = {normalize(character_id), name}
        candidates.update(word for word in name.split() if len(word) >= _MIN_NAME_WORD)
        for key in candidates:
            if key:
                keys.setdefault(key, set()).add(character_id)
    resolved: list[str] = []
    for item in requested:
        matches = keys.get(normalize(item), set())
        if len(matches) == 1:
            (character_id,) = matches
            if character_id not in resolved:
                resolved.append(character_id)
    return resolved


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
