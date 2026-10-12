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
    review: NarrationReview, story: str, turns: list[StageTurn]
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
    return verdict


def _unsupported(quote: str, turn_ids: list[str], story: str, known: set[str]) -> str:
    """Say why a finding cannot be checked against this candidate, or return nothing."""
    if not set(turn_ids) <= known:
        return "cites an unavailable turn"
    if quote and _normalized(quote) not in _normalized(story):
        return "quote is absent from the candidate"
    if not quote and not turn_ids:
        return "needs a prose quote or visible source"
    return ""


def _normalized(text: str) -> str:
    """Compare quotes without tripping on spacing or typographic quote marks."""
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    return " ".join(text.split()).casefold()


def review_turns(turns: list[StageTurn]) -> list[dict]:
    """Project only fields the selected narrative perspective has already authorized."""
    return [
        {
            key: getattr(turn, key)
            for key in ("id", "actor_id", "kind", "action", "speech", "thought")
        }
        for turn in turns
    ]
