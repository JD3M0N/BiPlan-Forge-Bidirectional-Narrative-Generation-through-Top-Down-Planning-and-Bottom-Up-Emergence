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

from .schemas import NarrationReview, StageTurn

# Findings that make the chapter tell something that did not happen. The rest are craft notes:
# they travel to the next attempt as corrections, but never cost the chapter its narrator.
BLOCKING_CODES = frozenset({"INVENTED_EVENT", "CONTRADICTION"})

_KEY_MARK = re.compile(r"\[clave\][ \t]*", re.I)
_THOUGHT_LABEL = re.compile(r"\[[^]\n]+? piensa:\s*([^]\n]*)\]")
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
# A stage direction is written in the present, so a narration that copies its opening words
# copies its tense. Measured on the 7.13 navigators run: the chapter told in the present
# reused 15 directions this way, every other chapter of that run and of 7.12 at most one.
_DIRECTION_WORDS = 4
_MIN_COPIED_DIRECTIONS = 3
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


def strip_markers(story: str) -> str:
    """Remove process labels a narrator copied from its log, keeping the prose around them."""
    cleaned = _THOUGHT_LABEL.sub(r"\1", _KEY_MARK.sub("", story))
    return "\n".join(line.rstrip() for line in cleaned.splitlines()).strip()


def editorial_verdict(
    review: NarrationReview, story: str, turns: list[StageTurn], language: str = ""
) -> EditorialVerdict:
    """Sort findings into blocking and advisory, dropping the ones the source cannot support."""
    known = {turn.id for turn in turns}
    verdict = EditorialVerdict()
    for finding in review.findings:
        reason = _unsupported(finding.quote, finding.turn_ids, story, known)
        line = f"{finding.code}: {finding.correction}"
        if reason:
            verdict.discarded.append(f"{line} ({reason})")
        elif finding.code in BLOCKING_CODES:
            verdict.blocking.append(line)
        else:
            verdict.advisory.append(line)
    if _INTERNAL_ID.search(story):
        verdict.blocking.append("INTERNAL_MARKER: remove internal identifiers from the prose")
    if _in_present(story, language) or _copies_directions(story, turns):
        verdict.blocking.append(
            "WRONG_TENSE: narrate in the past tense, dialogue tags included ('dijo', never "
            "'dice'), and curate the exchanges instead of rendering every turn"
        )
    return verdict


def _in_present(story: str, language: str) -> bool:
    """Say whether a Spanish chapter tags its dialogue in the present rather than the past."""
    if not language.strip().lower().startswith(("spanish", "espa")):
        return False
    present = len(_PRESENT_TAG.findall(story))
    return present >= _MIN_PRESENT_TAGS and present > len(_PAST_TAG.findall(story))


def _copies_directions(story: str, turns: list[StageTurn]) -> bool:
    """Say whether the narration outside dialogue copies the log's present-tense directions."""
    narration = " ".join(
        line for line in story.lower().splitlines() if not line.lstrip().startswith("—")
    )
    narration = " ".join(_WORD.findall(narration))
    copied = 0
    for turn in turns:
        words = _WORD.findall(turn.action.lower())[:_DIRECTION_WORDS]
        if len(words) == _DIRECTION_WORDS and " ".join(words) in narration:
            copied += 1
    return copied >= _MIN_COPIED_DIRECTIONS


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


def review_turns(turns: list[StageTurn]) -> list[dict]:
    """Project only fields the selected narrative perspective has already authorized."""
    return [
        {
            key: getattr(turn, key)
            for key in ("id", "actor_id", "kind", "action", "speech", "thought")
        }
        for turn in turns
    ]
