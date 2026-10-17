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
from .language import is_foreign
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
# A gesture is a tic when it shares this many words in a row with one the same actor made
# anywhere earlier in the play (7.16). REPEATED_ACTION's window of three missed them: in 7.15.2
# Ilse closed her fist on the pommel of her short sword three times, Gaspar struck the bulkhead
# with his knuckles four. Across the 7.12-7.15 runs this flags about one gesture in ten.
GESTURE_RUN = 3
# 7.17: four of the six tics flagged in the October runs were a place or a direction, not a
# gesture ("hacia grieta superior", "entrada del bosque", "senala hacia las"). A run that holds
# one of these words is where a gesture goes, so it never counts as the gesture repeated.
_GESTURE_FILLER = frozenset(
    "las los del hacia bajo tras junto frente encima debajo dentro fuera cerca lejos "
    "mientras luego hasta".split()
)
# A line restates a position when this much of its content words already came out of the same
# speaker's mouth earlier in the scene (7.15). REPETITION_THRESHOLD only sees near-verbatim
# lines; in the 7.14 navigators run Hanu made the same threat three times in other words.
# Across the four 7.12-7.14 runs this flags 6 of 140 lines, each a restatement on reading.
PARAPHRASE_CONTAINMENT = 0.3
# Fewer content words than this say too little to count as a position.
_MIN_PARAPHRASE_WORDS = 4
# A thought that opens like this is a plan, not subtext: the actor narrating its next move,
# which the narrator then turned into "decidido a..." (SIM-6). 7 of 48 thoughts in the 7.14
# navigators run. Spanish only, the language every measured run was written in.
_PLAN_THOUGHT = re.compile(r"^(?:debo|tengo que|necesito|voy a|hay que)\b", re.I)
# 7.17: a plan also comes dressed as a condition ("Si no lee el documento, tendré que
# obligarle"). Only a consequence the speaker will carry out counts - a plan verb or a verb in
# the first-person future. Of 297 thoughts opening with "Si" in the October runs, 28 have that
# shape; the other 269 are fears ("Si la piedra cede, el mar nos engullirá"), which is subtext.
_CONDITIONAL_PLAN = re.compile(
    r"^si\b[^.!?]*?,\s*(?:(?:lo|la|le|los|las|les|me|te|nos)\s+)?"
    r"(?:(?:debo|tengo que|necesito|voy a|hay que|podr[ée]|tendr[ée] que)\b|[^\W\d_]+ré\b)",
    re.I,
)
# 7.15.1: the plan also came as a second sentence ("Este miserable... Debo asegurar que..."), so
# each sentence is read on its own and only the plans are dropped.
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


def _is_plan(sentence: str) -> bool:
    """Say whether one sentence of a thought only announces the speaker's next move."""
    return bool(_PLAN_THOUGHT.match(sentence) or _CONDITIONAL_PLAN.match(sentence))


def _without_plans(thought: str) -> str:
    """Drop the sentences of a thought that only announce the next move, keeping the rest."""
    kept = [part for part in _SENTENCE.split(thought) if part and not _is_plan(part)]
    return " ".join(kept).strip()


# How many turns in a row on one tactic the actor may play before a fresh one is asked for.
TACTIC_RUN = 2
# A thought that says this much of what the speech already says is not subtext, only an echo.
THOUGHT_ECHO = 0.5
# The longest line that still reads as a turn rather than a speech. It lives here and never in a
# prompt, like every other figure the stage measures.
MAX_SPEECH_WORDS = 45

_WHITESPACE = re.compile(r"\s+")
_LEADING_DASHES = "—–-"
# Internal identifiers look like event-3 or chapter_2; a reader must never see one.
_INTERNAL_ID = re.compile(r"\b(?:event|chapter|scene|promise|beat)[-_]\d+\b", re.IGNORECASE)
# First-person markers in a stage direction: "me arrodillo" at the start and "la palma de mi
# mano" anywhere. Guessing Spanish conjugation from one word would reject honest third-person
# directions, so a verb counts only from the closed lists below.
_FIRST_PERSON = re.compile(r"^(?:me|yo)\b|\b(?:mi|mis|conmigo)\b", re.IGNORECASE)
# The first-person words a stage direction can lose without touching a verb.
_THIRD_PERSON = {"mi": "su", "mis": "sus", "conmigo": "consigo"}
_POSSESSIVE = re.compile(r"\b(?:mi|mis|conmigo)\b", re.IGNORECASE)
# 7.17: 11 of the 49 actions of 20261017-184641 opened on a first-person verb ("Golpeo",
# "Doy un paso"), which the markers above never saw. Each verb here was read in the actors'
# directions of the corpus, and each has one third-person form, so it is corrected in place.
# Words that are also a noun or a preposition ("bajo", "paso") stay out.
_FIRST_PERSON_VERBS = {
    "abro": "abre",
    "acaricio": "acaricia",
    "aferro": "aferra",
    "agarro": "agarra",
    "ajusto": "ajusta",
    "alzo": "alza",
    "anoto": "anota",
    "apoyo": "apoya",
    "aprieto": "aprieta",
    "arrojo": "arroja",
    "avanzo": "avanza",
    "camino": "camina",
    "cierro": "cierra",
    "clavo": "clava",
    "coloco": "coloca",
    "corro": "corre",
    "cruzo": "cruza",
    "dejo": "deja",
    "deslizo": "desliza",
    "despliego": "despliega",
    "doy": "da",
    "empiezo": "empieza",
    "empujo": "empuja",
    "entrego": "entrega",
    "escarbo": "escarba",
    "escupo": "escupe",
    "examino": "examina",
    "extiendo": "extiende",
    "giro": "gira",
    "golpeo": "golpea",
    "guardo": "guarda",
    "inclino": "inclina",
    "lanzo": "lanza",
    "levanto": "levanta",
    "mantengo": "mantiene",
    "masajeo": "masajea",
    "miro": "mira",
    "muestro": "muestra",
    "niego": "niega",
    "observo": "observa",
    "ofrezco": "ofrece",
    "pongo": "pone",
    "presiono": "presiona",
    "recojo": "recoge",
    "retiro": "retira",
    "retrocedo": "retrocede",
    "saco": "saca",
    "señalo": "señala",
    "sonrío": "sonríe",
    "sostengo": "sostiene",
    "sujeto": "sujeta",
    "suelto": "suelta",
    "suspiro": "suspira",
    "tomo": "toma",
    "toco": "toca",
}
# After "me", the reflexive ones, which become "se" plus the third person.
_REFLEXIVE_VERBS = {
    **_FIRST_PERSON_VERBS,
    "abalanzo": "abalanza",
    "acerco": "acerca",
    "agacho": "agacha",
    "alejo": "aleja",
    "aparto": "aparta",
    "arrodillo": "arrodilla",
    "asomo": "asoma",
    "desplomo": "desploma",
    "detengo": "detiene",
    "enderezo": "endereza",
    "interpongo": "interpone",
    "paso": "pasa",
    "planto": "planta",
    "quedo": "queda",
    "siento": "sienta",
    "vuelvo": "vuelve",
}
# Where a clause can begin a new verb of the actor's: the start, a comma, or a joining word,
# with an object pronoun that may come between it and the verb.
_CLAUSE_VERB = re.compile(
    r"(^|[,;]\s*|\b(?:y|e|mientras|luego|que|entonces)\s+)"
    r"(?:(me|yo|lo|la|los|las|le|les)\s+)?([^\W\d_]+)",
    re.IGNORECASE,
)
# Where one spoken sentence ends and the next begins.
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


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
    # A plan has the same single fix: the move itself is the turn (7.15).
    thought = _without_plans(thought)
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


def repair_form(turn: ActorTurnDraft) -> tuple[ActorTurnDraft, list[str]]:
    """Fix the form faults that have one correct fix, and name the rejection each one avoided.

    Two rejections used to bounce turns that only needed trimming, and two of them in a row
    skip the turn: three of the 7.8 lighthouse run's turns were lost to lines of 46 to 55 words.
    A line over the limit is cut at its last sentence end that fits; a stage direction that
    says "mi" or "mis" or "conmigo" gets the third person. Anything else is left for
    validate_turn to reject as before: a line with no sentence end inside the limit, or a
    direction that opens on "me" or "yo", which would need a verb conjugated to fix.
    """
    repairs: list[str] = []
    speech, action = turn.speech, turn.action
    if len(speech.split()) > MAX_SPEECH_WORDS:
        trimmed = _trim_to_sentences(speech)
        if trimmed:
            speech = trimmed
            repairs.append("LONG_SPEECH")
    if action:
        third = _third_person_verbs(_POSSESSIVE.sub(_third_person, action))
        if third != action and not _FIRST_PERSON.search(third):
            action = third
            repairs.append("FIRST_PERSON_ACTION")
    if not repairs:
        return turn, repairs
    return turn.model_copy(update={"speech": speech, "action": action}), repairs


def _trim_to_sentences(speech: str) -> str:
    """Keep the leading whole sentences that fit the limit, or nothing when the first does not."""
    kept: list[str] = []
    words = 0
    for sentence in _SENTENCE_END.split(speech.strip()):
        count = len(sentence.split())
        if words + count > MAX_SPEECH_WORDS:
            break
        kept.append(sentence)
        words += count
    return " ".join(kept)


def _third_person(match: re.Match[str]) -> str:
    """Turn one first-person possessive into the third person, keeping its capital."""
    word = match.group(0)
    replacement = _THIRD_PERSON[word.casefold()]
    return replacement.capitalize() if word[0].isupper() else replacement


def _third_person_verbs(action: str) -> str:
    """Conjugate the known first-person verbs of a direction in the third person (7.17)."""

    def replace(match: re.Match[str]) -> str:
        """Rewrite one clause-opening verb, with its pronoun, when the lists know it."""
        lead, pronoun, word = match.group(1), match.group(2) or "", match.group(3)
        reflexive = pronoun.casefold() == "me"
        third = (_REFLEXIVE_VERBS if reflexive else _FIRST_PERSON_VERBS).get(word.casefold())
        if third is None:
            return match.group(0)
        if reflexive:
            return f"{lead}{_capital_like('se', pronoun)} {third}"
        if pronoun.casefold() == "yo":
            return f"{lead}{_capital_like(third, pronoun)}"
        before = f"{pronoun} " if pronoun else ""
        return f"{lead}{before}{_capital_like(third, word)}"

    return _CLAUSE_VERB.sub(replace, action)


def _capital_like(word: str, model: str) -> str:
    """Return a word capitalized when the word it replaces was."""
    return word.capitalize() if model[:1].isupper() else word


def _first_person_verb(action: str) -> bool:
    """Say whether a direction opens a clause on a first-person verb the lists know."""
    for match in _CLAUSE_VERB.finditer(action):
        pronoun, word = (match.group(2) or "").casefold(), match.group(3).casefold()
        verbs = _REFLEXIVE_VERBS if pronoun == "me" else _FIRST_PERSON_VERBS
        if word in verbs:
            return True
    return False


def validate_turn(
    turn: ActorTurnDraft,
    *,
    previous_speech: list[str],
    previous_actions: list[str] | None = None,
    language: str = "",
    scene_speech: list[str] | None = None,
    play_actions: list[str] | None = None,
    scene_tactics: list[str] | None = None,
) -> None:
    """Accept one normalized turn, or raise a TurnIssue saying in English what to fix.

    scene_speech is what this speaker already said in the scene, and play_actions every gesture
    they made in the play; the engine passes both on a first attempt only, so a restated
    position or a tic costs one retry and never a stalled turn.
    """
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
    foreign = [
        label
        for label, text in (
            ("speech", turn.speech),
            ("action", turn.action),
            ("thought", turn.thought),
        )
        if is_foreign(text, language)
    ]
    if foreign:
        raise TurnIssue(
            "WRONG_LANGUAGE",
            f"the {', '.join(foreign)} is not in {language}; say, do and think everything in "
            f"{language}, the language of the fiction",
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
    if is_first_person_action(turn.action):
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
    restated = _restated(turn.speech, scene_speech or [])
    if restated is not None:
        raise TurnIssue(
            "RESTATED_POSITION",
            f"you already made this point in this scene ({restated!r}); do not argue it again: "
            "give ground, change tactic, ask something, or act",
        )
    _check_gesture(turn.action, previous_actions or [], play_actions or [])
    # 7.17: a third turn in a row on one tactic. In the October runs 57 % of the turns ordered,
    # demanded or threatened, with runs of three to six; a structured choice of move is what the
    # echo literature found to break the loop. First attempts only, like the other repetitions.
    recent = (scene_tactics or [])[-TACTIC_RUN:]
    if len(recent) == TACTIC_RUN and set(recent) == {turn.tactic}:
        raise TurnIssue(
            "TACTIC_RUN",
            f"you have played '{turn.tactic}' in your last turns and it has not worked; get what "
            "you want another way this time: ask, bargain, concede a little, lie, or act",
        )


def _check_gesture(action: str, recent: list[str], played: list[str]) -> None:
    """Reject a gesture the actor just made, or one that has become a tic over the play."""
    if _replays_gesture(action, recent):
        raise TurnIssue(
            "REPEATED_ACTION",
            "you already made this gesture; do something new, or say something without it",
        )
    tic = _tic(action, played)
    if tic:
        raise TurnIssue(
            "REPEATED_ACTION",
            f"you have already done this ({tic!r}); repeated, a gesture becomes a tic: show it "
            "another way, or act without it",
        )


def containment(earlier: str, later: str) -> float:
    """Return how much of an earlier line survives inside a later one, from 0 to 1."""
    first, second = set(tokens(earlier)), set(tokens(later))
    if not first:
        return 0.0
    return len(first & second) / len(first)


def is_first_person_action(action: str) -> bool:
    """Say whether a stage direction carries a first-person marker or a known first-person verb."""
    return bool(action and (_FIRST_PERSON.search(action) or _first_person_verb(action)))


def _replays_gesture(action: str, previous: list[str]) -> bool:
    """Say whether a new action replays one of the actor's own recent gestures."""
    if not action:
        return False
    return any(
        containment(earlier, action) >= ACTION_CONTAINMENT
        for earlier in previous[-REPETITION_WINDOW:]
        if earlier
    )


def _tic(action: str, earlier: list[str]) -> str:
    """Return the run of words a new action repeats from any earlier gesture, or nothing."""
    runs = set(_runs(tokens(action)))
    for gesture in earlier:
        for run in _runs(tokens(gesture)):
            if run in runs:
                return " ".join(run)
    return ""


def _runs(words: list[str]) -> list[tuple[str, ...]]:
    """Every GESTURE_RUN words in a row of a tokenized action that name the gesture itself."""
    last = len(words) - GESTURE_RUN
    runs = [tuple(words[index : index + GESTURE_RUN]) for index in range(last + 1)]
    return [run for run in runs if not _GESTURE_FILLER.intersection(run)]


def similarity(left: str, right: str) -> float:
    """Score lexical overlap between two lines, as the repetition rule measures it."""
    first, second = set(tokens(left)), set(tokens(right))
    if not first or not second:
        return 0.0
    return len(first & second) / len(first | second)


def echo_of(line: str, candidates: list[str]) -> float:
    """Return how closely one line echoes the nearest of a set, 0 when the set is empty."""
    return max((similarity(line, item) for item in candidates), default=0.0)


def _restated(speech: str, earlier: list[str]) -> str | None:
    """Return the earlier line of the scene a candidate restates in other words, or None."""
    words = set(tokens(speech))
    if len(words) < _MIN_PARAPHRASE_WORDS:
        return None
    for line in reversed(earlier):
        if len(words & set(tokens(line))) / len(words) >= PARAPHRASE_CONTAINMENT:
            return line[:80]
    return None


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


def settle_state_evidence(candidate: ActorTurnDraft) -> tuple[ActorTurnDraft, list[str]]:
    """Keep a changed private state only when its quote is in the turn, else drop the change.

    Until 7.16 an unsupported change rejected the whole turn: 24 of the 51 rejections of the
    7.12-7.16 runs, and twice in a row it cost Aleth her turn in the Raiz scene. The quote was
    compared byte for byte, so an accent or a quote mark was enough. The change is bookkeeping
    and the turn is the performance, so the turn stays and only the change is dropped.
    """
    changes = (
        candidate.goal_after,
        candidate.commitment_after,
        candidate.cover_story_after,
        candidate.change_condition_after,
    )
    if not any(changes):
        return candidate, []
    quote = normalize(candidate.state_evidence)
    if quote and any(
        quote in normalize(text) for text in (candidate.thought, candidate.action, candidate.speech)
    ):
        return candidate, []
    dropped = candidate.model_copy(
        update={
            "goal_after": "",
            "commitment_after": "",
            "cover_story_after": "",
            "change_condition_after": "",
        }
    )
    return dropped, ["STATE_CHANGE_DROPPED"]
