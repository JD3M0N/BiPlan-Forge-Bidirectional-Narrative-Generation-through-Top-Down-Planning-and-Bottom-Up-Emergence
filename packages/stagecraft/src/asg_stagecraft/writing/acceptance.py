"""Whether one Writer candidate may replace the draft it was asked to revise.

Pure and deterministic: the rules below never call a model and never read a measurement
that reached a prompt. A rejected candidate produces a diagnostic whose retry_instruction
is reinjected into the next attempt, so those strings stay in English like the rest of the
model-facing contract; the fallback warning is user-facing and stays in Spanish.
"""

from __future__ import annotations

from ..schemas import ChapterRevisionAttempt, RevisionNote, WriterCandidateDiagnostic
from .audit import word_count


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
