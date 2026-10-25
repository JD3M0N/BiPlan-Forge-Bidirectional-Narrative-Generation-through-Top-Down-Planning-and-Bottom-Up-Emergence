"""What a judge returns about a plan or a draft: checks, notes and verdicts."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from ..planning.catalog_types import ModelId


class ConstraintCheck(BaseModel):
    """Represent ConstraintCheck data and behavior."""

    constraint: str
    passed: bool
    notes: str = ""


class RevisionNote(BaseModel):
    """One actionable English-language instruction for plan or prose revision."""

    id: ModelId
    priority: Literal["critical", "major", "minor"]
    category: Literal[
        "user_constraint",
        "causal_continuity",
        "world_continuity",
        "character_motivation",
        "agency",
        "dramatic_structure",
        "pacing",
        "setup_payoff",
        "originality",
        "voice_style",
        "language",
    ]
    evidence: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    chapter_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)


class PlanReview(BaseModel):
    """Structured critique of a validated candidate story plan."""

    approved: bool
    strengths: list[str] = Field(default_factory=list)
    notes: list[RevisionNote] = Field(default_factory=list)

    @model_validator(mode="after")
    def approval_matches_notes(self) -> PlanReview:
        """Reject contradictory approvals that still contain actionable notes."""
        if self.approved and self.notes:
            raise ValueError("an approved plan review cannot contain revision notes")
        if not self.approved and not self.notes:
            raise ValueError("a rejected plan review must contain revision notes")
        return self
