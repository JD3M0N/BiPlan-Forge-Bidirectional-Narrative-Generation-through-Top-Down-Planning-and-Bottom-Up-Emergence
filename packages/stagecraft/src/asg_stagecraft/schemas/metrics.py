"""What a finished draft is judged and measured by, with the evidence behind it."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
)

from ..planning.catalog_types import ModelId
from ..planning.profiles import NarrativeProfile
from .promises import PromiseCheck
from .review import ConstraintCheck, RevisionNote


class StoryReview(BaseModel):
    """Represent StoryReview data and behavior."""

    strengths: list[str] = Field(default_factory=list)
    notes: list[RevisionNote] = Field(default_factory=list)
    constraint_checks: list[ConstraintCheck] = Field(default_factory=list)
    promise_checks: list[PromiseCheck] = Field(default_factory=list)


class ChapterCraftEvidence(BaseModel):
    """Craft deficits observed in one drafted chapter, worded for the critic."""

    chapter_id: ModelId
    observations: list[str] = Field(default_factory=list)


class CraftEvidenceArtifact(BaseModel):
    """Deterministic craft evidence and the exact block handed to the Drama Critic."""

    chapters: list[ChapterCraftEvidence] = Field(default_factory=list)
    prompt_block: str = ""


class ChapterMetrics(BaseModel):
    """Record observed chapter size and prose craft without defining a target."""

    chapter_id: ModelId
    words: int = Field(ge=0)
    events: int = Field(ge=0)
    paragraphs: int = Field(default=0, ge=0)
    sentences: int = Field(default=0, ge=0)
    dialogue_paragraphs: int = Field(default=0, ge=0)
    dialogue_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    words_per_sentence: float = Field(default=0.0, ge=0.0)
    words_per_paragraph: float = Field(default=0.0, ge=0.0)


class StoryMetrics(BaseModel):
    """Record observed story characteristics without budget compliance.

    ``words`` counts the whole Markdown document, headings included, while
    ``prose_words`` counts only the paragraphs the craft figures describe.
    """

    narrative_profile: NarrativeProfile
    words: int = Field(ge=0)
    chapters: int = Field(ge=0)
    events: int = Field(ge=0)
    prose_paragraphs: int = Field(default=0, ge=0)
    prose_sentences: int = Field(default=0, ge=0)
    prose_words: int = Field(default=0, ge=0)
    dash_paragraphs: int = Field(default=0, ge=0)
    quoted_paragraphs: int = Field(default=0, ge=0)
    dialogue_paragraphs: int = Field(default=0, ge=0)
    dialogue_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    words_per_sentence: float = Field(default=0.0, ge=0.0)
    words_per_paragraph: float = Field(default=0.0, ge=0.0)
    chapter_bodies_recovered: bool = True
    chapter_metrics: list[ChapterMetrics] = Field(default_factory=list)
