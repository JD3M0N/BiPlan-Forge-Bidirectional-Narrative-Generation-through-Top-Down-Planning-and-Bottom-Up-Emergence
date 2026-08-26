"""Public Top-Down 4.1 contracts.

The module is intentionally a compatibility façade for consumers.  Factual
domain, STORYLINE, and post-STORYLINE craft types live in separate modules so
their dependency direction can be tested.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .craft_models import *  # noqa: F403 - public compatibility surface
from .domain import *  # noqa: F403 - public compatibility surface
from .storyline.models import *  # noqa: F403 - public compatibility surface


AuditVerdict = Literal["pass", "fail", "not_applicable"]


class CraftAuditAnswer(BaseModel):
    question_id: str
    category: Literal[
        "promise", "chapter_craft", "character", "try_fail", "constraint",
        "taxonomy", "language", "coherence", "pacing", "engagement",
        "satisfaction", "global",
    ]
    subject_id: str
    question: str
    chapter_ids: list[str] = Field(default_factory=list)
    blocking: bool = True
    verdict: AuditVerdict
    evidence: str
    issue: str = ""
    revision_instruction: str = ""

    @model_validator(mode="after")
    def failures_are_actionable(self) -> "CraftAuditAnswer":
        if self.verdict == "fail" and (
            not self.issue.strip() or not self.revision_instruction.strip()
        ):
            raise ValueError("failed audit answers require an issue and revision instruction")
        return self


class CraftAuditArtifact(BaseModel):
    answers: list[CraftAuditAnswer]
    summary: str

    @property
    def failed_blocking_ids(self) -> list[str]:
        return [
            answer.question_id for answer in self.answers
            if answer.blocking and answer.verdict == "fail"
        ]

    @property
    def passed(self) -> bool:
        return not self.failed_blocking_ids

    @property
    def revision_instructions(self) -> list[str]:
        return [answer.revision_instruction for answer in self.answers if answer.verdict == "fail"]

    @property
    def affected_chapter_ids(self) -> list[str]:
        return sorted({
            chapter_id for answer in self.answers if answer.verdict == "fail"
            for chapter_id in answer.chapter_ids
        })


class CraftRevisionAttempt(BaseModel):
    attempt: int = Field(ge=0)
    text_file: str
    audit_file: str
    passed: bool
    repaired_chapter_ids: list[str] = Field(default_factory=list)
    failed_blocking_ids: list[str] = Field(default_factory=list)
    failed_advisory_ids: list[str] = Field(default_factory=list)


class CraftRevisionHistory(BaseModel):
    selected_attempt: int = Field(ge=0)
    exhausted: bool
    attempts: list[CraftRevisionAttempt] = Field(default_factory=list)


class LengthAuditEntry(BaseModel):
    chapter_id: str | None = None
    target_words: int
    minimum_words: int
    maximum_words: int
    actual_words: int
    within_tolerance: bool


class LengthAuditArtifact(BaseModel):
    chapters: list[LengthAuditEntry] = Field(default_factory=list)
    total: LengthAuditEntry


class ErrorReport(BaseModel):
    run_id: str
    code: str
    stage: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class LLMUsageRecord(BaseModel):
    call_id: str
    operation: str
    stage: str = "unknown"
    attempt: int = Field(default=1, ge=1)
    status: Literal["succeeded", "failed"] = "succeeded"
    error_code: str | None = None
    model: str
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_seconds: float = 0
    prompt_tokens: int = 0
    candidate_tokens: int = 0
    thoughts_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    wait_seconds: float = 0
    retries: int = 0


class LLMUsageArtifact(BaseModel):
    records: list[LLMUsageRecord] = Field(default_factory=list)
    calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_wait_seconds: float = 0


class RunMetadata(BaseModel):
    run_id: str
    model: str
    created_at: datetime
    updated_at: datetime
    status: Literal["running", "completed", "failed", "recovery_pending"] = "running"
    completed_stages: list[str] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    error_stage: str | None = None
    warnings: list[str] = Field(default_factory=list)
    pipeline_version: str = "4.1"
