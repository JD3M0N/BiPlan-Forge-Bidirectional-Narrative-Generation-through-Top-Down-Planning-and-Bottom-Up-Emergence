"""An approval counts only with a quote the draft contains (7.17, anchored_critic; TD-1).

The Drama Critic approved 695 of 696 constraint checks in the 6.x runs and 18 of 18 in the
7.10 narratives, one of them "nearly defeats" over a chapter where the rival says "you beat
me". Its evidence was a paraphrase, often in English. Feedback from a model is specific but
does not know when to criticise instead of praise (ACL 2025), so the verdict is not taken on
its word: every constraint passed and every promise paid must quote the draft, and this module
looks the quote up. A quote the draft does not contain makes the check unjudged, and unjudged
counts against the story, as an unjudged promise already did.
"""

from __future__ import annotations

from ..schemas import ConstraintCheck, PromiseCheck, RevisionNote, StoryReview

# A quote shorter than this proves nothing: "dijo que no" is in every story.
MIN_QUOTE_WORDS = 4

_TYPOGRAPHY = str.maketrans(
    {"“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "—": "-", "–": "-"}
)


def _normalized(text: str) -> str:
    """Compare quotes without tripping on spacing, quote styles, dashes or case."""
    return " ".join(text.translate(_TYPOGRAPHY).replace('"', "").split()).casefold()


def quoted(quote: str, text: str) -> bool:
    """Say whether a quote is long enough to prove something and appears in the text."""
    words = quote.strip().strip('"«»“”').split()
    return len(words) >= MIN_QUOTE_WORDS and _normalized(" ".join(words)) in _normalized(text)


def anchor_review(review: StoryReview, draft: str) -> tuple[StoryReview, dict]:
    """Unjudge every approval whose quote the draft lacks, and say what was checked."""
    constraints: list[ConstraintCheck] = []
    promises: list[PromiseCheck] = []
    notes = list(review.notes)
    record: dict = {"constraints": [], "promises": [], "notes": []}
    for index, check in enumerate(review.constraint_checks, 1):
        found = quoted(check.notes, draft)
        record["constraints"].append(
            {"constraint": check.constraint, "passed": check.passed, "found": found}
        )
        if check.passed and not found:
            check = check.model_copy(
                update={"passed": False, "notes": "no passage of the draft shows it"}
            )
            notes.append(
                RevisionNote(
                    id=f"unanchored-constraint-{index}",
                    priority="major",
                    category="user_constraint",
                    evidence=f"No passage of the draft shows this requirement: {check.constraint}",
                    instruction=(
                        "Make this requirement visible in the chapter where it belongs, through "
                        f"what happens or is said: {check.constraint}"
                    ),
                )
            )
        constraints.append(check)
    for check in review.promise_checks:
        found = quoted(check.evidence, draft)
        record["promises"].append(
            {"promise_id": check.promise_id, "verdict": check.verdict, "found": found}
        )
        if check.verdict != "broken" and not found:
            check = check.model_copy(
                update={
                    "verdict": "broken",
                    "evidence": f"[sin cita en el borrador] {check.evidence}",
                }
            )
        promises.append(check)
    record["notes"] = [
        {"id": note.id, "found": quoted(note.evidence, draft)} for note in review.notes
    ]
    anchored = review.model_copy(
        update={"constraint_checks": constraints, "promise_checks": promises, "notes": notes}
    )
    return anchored, record
