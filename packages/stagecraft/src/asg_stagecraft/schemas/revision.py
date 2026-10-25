"""The record of asking the Writer again: candidates, attempts and the report."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)

from ..planning.catalog_types import ModelId


class WriterCandidateDiagnostic(BaseModel):
    """Explain why one Writer candidate was rejected and how to correct it."""

    code: Literal[
        "EMPTY_CHAPTER_BODY",
        "MARKDOWN_HEADINGS",
        "UNCHANGED_SIGNIFICANT_NOTES",
        "INVALID_SCRIPT_ACT",
        "MERGED_PARAGRAPHS",
        "LENGTHENED_WITHOUT_CAUSE",
        "WORSE_CRAFT",
        "NOTE_NOT_APPLIED",
    ]
    message: str
    retry_instruction: str
    actual_words: int
    # 7.18: the critical or major notes no accepted edit answered, for NOTE_NOT_APPLIED.
    note_ids: list[str] = Field(default_factory=list)


class ChapterRevisionAttempt(BaseModel):
    """Record the auditable outcome of one bounded Writer call."""

    attempt: int = Field(ge=1)
    status: Literal["accepted", "rejected", "failed"]
    artifact: str | None = None
    diagnostic: WriterCandidateDiagnostic | None = None
    exception_type: str | None = None


class ChapterRevisionResult(BaseModel):
    """Summarize every Writer attempt and the chapter body ultimately delivered."""

    chapter_id: ModelId
    chapter_index: int = Field(ge=1)
    note_ids: list[str] = Field(default_factory=list)
    draft_words: int
    attempts: list[ChapterRevisionAttempt] = Field(default_factory=list)
    # 7.18: best_candidate is a rejected attempt that still beat the draft, named by final_attempt.
    final_source: Literal["revision", "best_candidate", "draft"]
    final_words: int
    final_attempt: int | None = None
    warning_code: (
        Literal["WRITER_REVISION_REJECTED", "WRITER_BEST_CANDIDATE", "SCRIPT_REVISION_REJECTED"]
        | None
    ) = None


class RevisionReport(BaseModel):
    """Persist the complete chapter-level Writer decision trail."""

    chapters: list[ChapterRevisionResult] = Field(default_factory=list)
