"""Validate editorial findings against the exact visible source and prose."""

from __future__ import annotations

import re

from .schemas import NarrationReview, StageTurn


def editorial_issues(review: NarrationReview, story: str, turns: list[StageTurn]) -> list[str]:
    """A reviewer cannot reject a chapter using a nonexistent quote or an unseen turn."""
    known = {turn.id for turn in turns}
    issues = []
    for finding in review.findings:
        if not set(finding.turn_ids) <= known:
            raise ValueError("editorial finding cites an unavailable turn")
        if finding.quote and finding.quote not in story:
            raise ValueError("editorial quote is absent from the candidate")
        if not finding.quote and not finding.turn_ids:
            raise ValueError("editorial finding needs a prose quote or visible source")
        issues.append(f"{finding.code}: {finding.correction}")
    if re.search(r"\[clave\]|\b(?:chapter|scene|event)[_-]\d+|\[[^]\n]+ piensa:", story, re.I):
        issues.append("INTERNAL_MARKER: remove process labels and render thoughts as prose")
    return issues


def review_turns(turns: list[StageTurn]) -> list[dict]:
    """Project only fields the selected narrative perspective has already authorized."""
    return [
        {
            key: getattr(turn, key)
            for key in ("id", "actor_id", "kind", "action", "speech", "thought")
        }
        for turn in turns
    ]
