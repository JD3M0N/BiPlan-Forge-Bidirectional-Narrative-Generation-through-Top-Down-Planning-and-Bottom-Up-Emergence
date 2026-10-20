"""Validate editorial findings against the exact visible source and prose.

Since 7.12 a finding that cannot be checked is discarded rather than fatal, and only findings
that change what happened block a chapter. In 7.10 a reviewer that paraphrased its quote, or
flagged a tense slip, sent half the chapters of the friends' study to the deterministic
fallback (7 of 14, against 0 of 50 before the review existed), even when the narrated attempt
was sound prose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .narration import opens_with_direction, shares_run
from .schemas import NarrationFinding, NarrationReview, StageTurn

# Findings that make the chapter tell something that did not happen. The rest are craft notes:
# they travel to the next attempt as corrections, but never cost the chapter its narrator.
BLOCKING_CODES = frozenset({"INVENTED_EVENT", "CONTRADICTION"})
# How much each blocking finding costs a leftover attempt when none was accepted (7.17). A tense
# or a marker the code measured spoils the whole chapter; a reviewer's contradiction is often one
# slip. In 20261017-184650 a tie on one finding each shipped the later attempt, told in the
# present with 16 "dice", over one whose only finding was a single untranslated word.
_SEVERITY = {
    "WRONG_TENSE": 3,
    "COPIED_DIRECTION": 3,
    "INTERNAL_MARKER": 3,
    "INVENTED_EVENT": 2,
    "DUPLICATED_LINE": 2,
    "CONTRADICTION": 1,
}
# A line the narrator only read as a retelling cannot reach the prose whole by itself. In the
# 7.19 islands run a reviewer's correction carried it there, and the chapter told it twice: the
# retelling, then the line. Six words in a row is a phrase of the line, not a shared idiom.
_DUPLICATE_RUN = 6
# The fixed repair each code sends forward when the reviewer's own correction quoted the log.
# In the 7.19 islands run "Hanu dice textualmente: <the whole line>" reached the next attempt.
_LOG_FREE_REPAIR = {
    "INVENTED_EVENT": "rewrite this passage so it tells only what the log records, in your own "
    "words",
    "CONTRADICTION": "make this passage agree with the cited turn, in your own words",
}
_DEFAULT_REPAIR = "revise this passage in your own words"

_KEY_MARK = re.compile(r"\[clave\][ \t]*", re.I)
_THOUGHT_LABEL = re.compile(r"\[[^]\n]+? piensa:\s*([^]\n]*)\]")
_WRAPPED_LINE = re.compile(r"^[ \t]*\(([^()\n]+)\)[ \t]*$", re.M)
_SCENE_LABEL = re.compile(r"^[ \t]*\[escena:[^]\n]*\][ \t]*\n?", re.M | re.I)
_INTERNAL_ID = re.compile(r"\b(?:chapter|scene|event)[_-]\d+", re.I)
# Spanish dialogue tags after a dash: present-tense speech verbs, and any preterite in -o.
# Every voice narrates in the past; in 7.12.1 a chapter came back as a dash line and
# "dice Ines" turn after turn, a present-tense transcript next to a chapter in the past,
# and the review let it through.
_PRESENT_TAG = re.compile(
    r"—\s*(?:dice|pregunta|responde|contesta|murmura|susurra|grita|exclama|añade|"
    r"replica|ordena|insiste)\b",
    re.I,
)
_PAST_TAG = re.compile(r"—\s*\w+ó\b", re.I)
# Below this many present tags a chapter has not settled into the present, it slipped once.
_MIN_PRESENT_TAGS = 3
# How many words of a pasted paragraph a COPIED_DIRECTION finding quotes to point at it.
_OPENING_WORDS = 6
# Chapters told in the past still share an opening with one direction now and then ("con un
# gesto brusco"); measured on 7.12 and 7.13, at most one each. Two pasted paragraphs block.
MIN_COPIED_DIRECTIONS = 2
_PARAGRAPHS = re.compile(r"\n[ \t]*\n+")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass
class EditorialVerdict:
    """What a review means for one candidate chapter once checked against the source."""

    blocking: list[str] = field(default_factory=list)
    advisory: list[str] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        """A chapter is publishable when nothing it tells contradicts the log."""
        return not self.blocking

    @property
    def issues(self) -> list[str]:
        """Every correction worth sending to the next attempt, blocking ones first."""
        return [*self.blocking, *self.advisory]

    def as_record(self) -> dict:
        """The verdict as stored next to the review on disk."""
        return {
            "blocking": self.blocking,
            "advisory": self.advisory,
            "discarded": self.discarded,
            "accepted": self.accepted,
        }


def severity(blocking: list[str]) -> int:
    """Weigh the blocking findings of one attempt, the measured ones above the reviewer's."""
    return sum(_SEVERITY.get(line.split(":", 1)[0], 1) for line in blocking)


def strip_markers(story: str) -> str:
    """Remove process labels a narrator copied from its log, keeping the prose around them."""
    cleaned = _THOUGHT_LABEL.sub(r"\1", _KEY_MARK.sub("", story))
    # 7.16: a world event marked key was copied whole, parentheses and all, as a paragraph.
    cleaned = _WRAPPED_LINE.sub(r"\1", cleaned)
    # 7.20: the label that opens each scene of the log is for the narrator, never the reader.
    cleaned = _SCENE_LABEL.sub("", cleaned)
    return _dialogue_apart("\n".join(line.rstrip() for line in cleaned.splitlines()).strip())


def _dialogue_apart(story: str) -> str:
    """Give every line of dialogue a paragraph of its own, as the dash convention expects.

    The first 7.20 replay glued lines to the narration before them with a single line break,
    which Markdown renders as one paragraph.
    """
    lines = story.splitlines()
    spaced: list[str] = []
    for index, line in enumerate(lines):
        if index and line.lstrip().startswith("—") and lines[index - 1].strip():
            spaced.append("")
        elif index and lines[index - 1].lstrip().startswith("—") and line.strip():
            spaced.append("")
        spaced.append(line)
    return "\n".join(spaced)


def editorial_verdict(
    review: NarrationReview,
    story: str,
    turns: list[StageTurn],
    language: str = "",
    reports: dict[str, str] | None = None,
) -> EditorialVerdict:
    """Sort findings into blocking and advisory, dropping the ones the source cannot support.

    ``reports`` are the retellings the narrator read in place of whole lines (7.16). Since 7.20
    a finding is checked against them too: in the 7.19 islands run 7 of 10 blocking findings
    called the reporter's own retellings invented, and every chapter shipped as a leftover.
    """
    reports = reports or {}
    known = {turn.id for turn in turns}
    verdict = EditorialVerdict()
    for finding in review.findings:
        line = f"{finding.code}: {_repair_text(finding, turns)}"
        reason = _unsupported(finding.quote, finding.turn_ids, story, known) or _grounded(
            finding, turns, reports
        )
        if reason:
            verdict.discarded.append(f"{line} ({reason})")
        elif finding.code in BLOCKING_CODES and (
            finding.code != "CONTRADICTION" or finding.turn_ids
        ):
            verdict.blocking.append(line)
        else:
            # A contradiction that names no turn has nothing to contradict: in the 7.19 islands
            # run the only one was a tense complaint, which the review prompt rules out.
            verdict.advisory.append(line)
    verdict.blocking.extend(_duplicated_lines(story, turns, reports))
    if _INTERNAL_ID.search(story):
        verdict.blocking.append("INTERNAL_MARKER: remove internal identifiers from the prose")
    if _in_present(story, language) or narrative_tense(story, language) == "imperfect":
        verdict.blocking.append(
            "WRONG_TENSE: narrate in the past tense, dialogue tags included ('dijo', never "
            "'dice'), and curate the exchanges instead of rendering every turn"
        )
    pasted = copied_directions(story, turns)
    if len(pasted) >= MIN_COPIED_DIRECTIONS:
        # 7.20: until now this was a WRONG_TENSE, which named no paragraph. In the 7.19 islands
        # run the chapter was in the preterite and three pasted paragraphs were not.
        verdict.blocking.append(
            "COPIED_DIRECTION: these paragraphs paste a stage direction, in the present: "
            + "; ".join(f'"{opening}..."' for opening in pasted)
            + ". Retell each one in the past tense and in your own words"
        )
    return verdict


def _in_present(story: str, language: str) -> bool:
    """Say whether a Spanish chapter tags its dialogue in the present rather than the past."""
    if not language.strip().lower().startswith(("spanish", "espa")):
        return False
    present = len(_PRESENT_TAG.findall(story))
    return present >= _MIN_PRESENT_TAGS and present > len(_PAST_TAG.findall(story))


# Craft observations a narrated chapter is measured on (7.15). Never a reason to reject: an
# accepted first attempt that trips one is narrated once more with the observation as a note.
# Measured on the 7.13 and 7.14 navigators runs, whose chapters copied 13 of 13 and 18 of 18
# lines verbatim and tagged 16 of 18 with a speech verb; the 7.12 chapters copied at most 9.
_MIN_LINES_MEASURED = 8
_TRANSCRIBED_SHARE = 0.9
_TAGGED_SHARE = 0.7
_QUOTED_CHARS = 60
_SPEECH_TAG = re.compile(r"—\s*(?:dijo|\w+(?:ó|ió))\b", re.I)


def craft_findings(story: str, turns: list[StageTurn]) -> list[str]:
    """Measure whether a chapter transcribes the log, tags every line or drops a world event."""
    findings = _dropped_events(story, turns)
    lines = [line.strip() for line in story.splitlines() if line.lstrip().startswith("—")]
    if len(lines) < _MIN_LINES_MEASURED:
        return _with_guard(findings)
    text = _normalized(story)
    verbatim = sum(
        1
        for turn in turns
        if len(turn.speech.split()) >= 6 and _normalized(turn.speech)[:_QUOTED_CHARS] in text
    )
    if verbatim >= _TRANSCRIBED_SHARE * len(lines):
        findings.append(
            "TRANSCRIBED: the chapter copies nearly every line of the log; keep the lines the "
            "scene turns on, cut or summarize the rest, and let several exchanges pass in one "
            "sentence of narration"
        )
    tagged = sum(1 for line in lines if _SPEECH_TAG.search(line[1:]))
    if tagged >= _TAGGED_SHARE * len(lines):
        findings.append(
            "TAGGED: almost every line carries a speech verb, any of them ('dijo', 'advirtió', "
            "'replicó'); swapping one verb for another is not the fix: tag a line only when "
            "the speaker would be unclear, and otherwise let a gesture or nothing follow it"
        )
    return _with_guard(findings)


def _with_guard(findings: list[str]) -> list[str]:
    """Add the note that says what a second attempt must not change, when there are notes."""
    if not findings:
        return []
    # 7.15: the second attempt answered these notes by moving the chapter into the imperfect.
    return [
        *findings,
        "KEEP: narrate in the same past tense (the preterite) and keep every event, line and "
        "choice the chapter already got right",
    ]


# A world event is told when the prose carries enough of the words only it used. Words are
# compared by their first letters, so "sacudida" matches "sacudió". The only world event of the
# 7.15.2 finale (a violent jolt that turned the argument) shared none of them with its chapter.
_EVENT_WORD = 6
_EVENT_STEM = 5
_EVENT_SHARE = 0.25


def _dropped_events(story: str, turns: list[StageTurn]) -> list[str]:
    """Name the world events a chapter leaves out, as notes for one more attempt."""
    told = _stems(story)
    spoken = _stems(
        " ".join(f"{turn.action} {turn.speech}" for turn in turns if turn.kind != "world")
    )
    findings = []
    for turn in turns:
        if turn.kind != "world":
            continue
        own = [stem for stem in _stems_in_order(turn.action) if stem not in spoken]
        if own and sum(stem in told for stem in own) < _EVENT_SHARE * len(own):
            findings.append(
                f"DROPPED_EVENT: the chapter leaves out something the world did ({turn.action}); "
                "tell it where it happened, it is what the characters react to"
            )
    return findings


def _stems(text: str) -> set[str]:
    """The stems of a text's long words, for telling whether an event is in the prose."""
    return set(_stems_in_order(text))


def _stems_in_order(text: str) -> list[str]:
    """The stems of a text's long words, in order."""
    return [word[:_EVENT_STEM] for word in _WORD.findall(text.lower()) if len(word) >= _EVENT_WORD]


# The tense a chapter narrates in, read from third-person verb endings outside the dialogue.
# Measured on the narrated chapters of 7.12 to 7.15: every chapter in the preterite has at most
# about as many -aba/-ia forms as -o/-io ones (one run 21 to 30, with long background
# descriptions), and the 7.15 chapter that slid into the imperfect had 0 to 32.
_PRETERITE = re.compile(r"(?:ó|ió)$")
_IMPERFECT = re.compile(r"(?:aba|ía)$")
_TENSE_MARGIN = 2
_MIN_TENSE_VERBS = 15


def narrative_tense(story: str, language: str = "Spanish") -> str:
    """Return 'preterite' or 'imperfect' when a Spanish chapter plainly narrates in one, or ''."""
    if not language.strip().lower().startswith(("spanish", "espa")):
        return ""
    narration = " ".join(line for line in story.splitlines() if not line.lstrip().startswith("—"))
    words = [word.lower() for word in _WORD.findall(narration)]
    preterite = sum(bool(_PRETERITE.search(word)) for word in words)
    imperfect = sum(bool(_IMPERFECT.search(word)) for word in words)
    if imperfect >= _MIN_TENSE_VERBS and imperfect >= _TENSE_MARGIN * max(preterite, 1):
        return "imperfect"
    if preterite >= _MIN_TENSE_VERBS and preterite >= _TENSE_MARGIN * max(imperfect, 1):
        return "preterite"
    return ""


def copied_directions(story: str, turns: list[StageTurn]) -> list[str]:
    """Return the opening words of every narration paragraph that pastes a stage direction."""
    actions = [turn.action for turn in turns if turn.action]
    pasted = []
    for block in _PARAGRAPHS.split(story.strip()):
        if not block.strip() or block.lstrip().startswith("—"):
            continue
        if any(opens_with_direction(block, action) for action in actions):
            pasted.append(" ".join(block.split()[:_OPENING_WORDS]))
    return pasted


def _grounded(finding: NarrationFinding, turns: list[StageTurn], reports: dict[str, str]) -> str:
    """Say which source an 'invented' passage actually comes from, or return nothing."""
    if finding.code != "INVENTED_EVENT" or not finding.quote:
        return ""
    for turn in turns:
        sources = (turn.speech, turn.action, turn.thought, reports.get(turn.id, ""))
        if any(source and shares_run(finding.quote, source) for source in sources):
            return f"grounded in {turn.id}"
    return ""


def _repair_text(finding: NarrationFinding, turns: list[StageTurn]) -> str:
    """Return the correction to send forward, never one that hands the narrator a log line."""
    if not any(turn.speech and shares_run(finding.correction, turn.speech) for turn in turns):
        return finding.correction
    repair = _LOG_FREE_REPAIR.get(finding.code, _DEFAULT_REPAIR)
    return f'"{finding.quote}": {repair}' if finding.quote else repair


def _duplicated_lines(story: str, turns: list[StageTurn], reports: dict[str, str]) -> list[str]:
    """Flag a line told twice: once as its retelling and once in the speaker's own words."""
    findings = []
    for turn in turns:
        report = reports.get(turn.id, "")
        if (
            report
            and turn.speech
            and shares_run(story, report)
            and shares_run(story, turn.speech, _DUPLICATE_RUN)
        ):
            findings.append(
                f'DUPLICATED_LINE: "{report}" is told twice, as a summary and again in the '
                "speaker's words; keep the summary and cut the repetition"
            )
    return findings


def _unsupported(quote: str, turn_ids: list[str], story: str, known: set[str]) -> str:
    """Say why a finding cannot be checked against this candidate, or return nothing."""
    if not set(turn_ids) <= known:
        return "cites an unavailable turn"
    if quote and _normalized(quote) not in _normalized(story):
        return "quote is absent from the candidate"
    if not quote and not turn_ids:
        return "needs a prose quote or visible source"
    return ""


_TYPOGRAPHY = str.maketrans(
    {"“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "—": "-", "–": "-"}
)
_DASH_SPACING = re.compile(r" ?- ?")


def _normalized(text: str) -> str:
    """Compare quotes without tripping on spacing, quote styles or dialogue dashes."""
    spaced = " ".join(text.translate(_TYPOGRAPHY).split())
    return _DASH_SPACING.sub("-", spaced).casefold()


def review_turns(turns: list[StageTurn], retold: dict[str, str] | None = None) -> list[dict]:
    """Project only fields the selected narrative perspective has already authorized.

    A turn the narrator read as a retelling carries it as ``retold_as`` (7.20), so the reviewer
    knows that sentence is the line in indirect style and not an invention.
    """
    retold = retold or {}
    projected = []
    for turn in turns:
        item = {
            key: getattr(turn, key)
            for key in ("id", "actor_id", "kind", "action", "speech", "thought")
        }
        if retold.get(turn.id):
            item["retold_as"] = retold[turn.id]
        projected.append(item)
    return projected
