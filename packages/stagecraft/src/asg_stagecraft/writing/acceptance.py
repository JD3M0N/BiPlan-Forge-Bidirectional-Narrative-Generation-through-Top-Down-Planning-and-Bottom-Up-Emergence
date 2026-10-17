"""Whether one Writer candidate may replace the draft it was asked to revise.

Pure and deterministic: the rules below never call a model and never read a measurement
that reached a prompt. A rejected candidate produces a diagnostic whose retry_instruction
is reinjected into the next attempt, so those strings stay in English like the rest of the
model-facing contract; the fallback warning is user-facing and stays in Spanish.
"""

from __future__ import annotations

from asg_core import prose_paragraphs

from ..schemas import ChapterRevisionAttempt, RevisionNote, WriterCandidateDiagnostic
from .audit import word_count
from .craft_evidence import chapter_observations

# 7.17 (TD-3): a rewrite that keeps less than this share of the draft's paragraphs merged them.
# In 7.10 the one chapter the Writer touched went from 27 paragraphs to 13 and shipped.
MIN_PARAGRAPH_SHARE = 0.7
# A rewrite may grow by this share at most unless a note asks for something to be staged:
# in 6.2, 66 of 69 revised chapters came back longer, by a median of 82 words.
MAX_GROWTH = 1.15
# The note categories that ask for a beat to be added, which can rightly lengthen a chapter.
_STAGING = frozenset({"pacing", "dramatic_structure", "setup_payoff", "user_constraint"})


def writer_candidate_issue(
    candidate: str,
    draft_body: str,
    notes: list[RevisionNote],
) -> WriterCandidateDiagnostic | None:
    """Explain why a Writer candidate cannot replace the draft."""
    actual_words = word_count(candidate)
    if not candidate.strip():
        return WriterCandidateDiagnostic(
            code="EMPTY_CHAPTER_BODY",
            message="the chapter body is empty",
            retry_instruction="Write a complete chapter body that fulfills the planned events.",
            actual_words=actual_words,
        )
    if any(line.lstrip().startswith("#") for line in candidate.splitlines()):
        return WriterCandidateDiagnostic(
            code="MARKDOWN_HEADINGS",
            message="the chapter body contains Markdown headings",
            retry_instruction="Remove every Markdown heading while preserving the prose body.",
            actual_words=actual_words,
        )
    significant = any(note.priority in {"critical", "major"} for note in notes)
    if significant and candidate.strip() == draft_body.strip():
        return WriterCandidateDiagnostic(
            code="UNCHANGED_SIGNIFICANT_NOTES",
            message="the text is unchanged despite critical or major revision notes",
            retry_instruction="Apply every critical and major note with visible prose changes.",
            actual_words=actual_words,
        )
    if draft_body.strip():
        return _degraded(candidate, draft_body, notes, actual_words)
    return None


def _degraded(
    candidate: str, draft_body: str, notes: list[RevisionNote], actual_words: int
) -> WriterCandidateDiagnostic | None:
    """Explain how a rewrite is worse than its draft in what the code can measure (7.17)."""
    drafted = len(prose_paragraphs(draft_body))
    if len(prose_paragraphs(candidate)) < MIN_PARAGRAPH_SHARE * drafted:
        return WriterCandidateDiagnostic(
            code="MERGED_PARAGRAPHS",
            message="the rewrite merged the draft's paragraphs into blocks",
            retry_instruction=(
                "Keep the paragraph breaks of the original: a new paragraph for each new "
                "speaker or shift of attention. Change only what the notes ask for."
            ),
            actual_words=actual_words,
        )
    staging = any(
        note.category in _STAGING and note.priority in {"critical", "major"} for note in notes
    )
    if not staging and actual_words > MAX_GROWTH * word_count(draft_body):
        return WriterCandidateDiagnostic(
            code="LENGTHENED_WITHOUT_CAUSE",
            message="the rewrite grew although no note asked for anything to be staged",
            retry_instruction=(
                "Apply the notes by replacing and cutting, not by adding: the chapter should "
                "come back about as long as the original, or shorter."
            ),
            actual_words=actual_words,
        )
    added = set(chapter_observations(candidate)) - set(chapter_observations(draft_body))
    if added:
        return WriterCandidateDiagnostic(
            code="WORSE_CRAFT",
            message="the rewrite shows craft problems the draft did not have",
            retry_instruction="Revise again without introducing: " + "; ".join(sorted(added)) + ".",
            actual_words=actual_words,
        )
    return None


def writer_fallback_warning(
    chapter_index: int,
    draft_words: int,
    attempts: list[ChapterRevisionAttempt],
) -> str:
    """Build a concise Spanish warning from the structured rejection trail."""
    reasons = [
        item.diagnostic.code if item.diagnostic is not None else item.exception_type
        for item in attempts
        if item.diagnostic is not None or item.exception_type is not None
    ]
    codes = ", ".join(reason for reason in reasons if reason) or "WRITER_EXCEPTION"
    return (
        "[WRITER_REVISION_REJECTED] Capítulo "
        f"{chapter_index}: no hubo una revisión válida tras {len(attempts)} intentos "
        f"({codes}). Se entregó el borrador de {draft_words} palabras."
    )
