"""Data contracts for the Top-Down 6.0 artifact pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .profiles import NarrativeProfile
from .version import GENERATOR_NAME, GENERATOR_VERSION, PIPELINE_VERSION

ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class StoryRequest(BaseModel):
    """Represent StoryRequest data and behavior."""

    model_config = ConfigDict(extra="forbid")

    original_prompt: str
    processed_prompt: str = ""
    title: str = Field(min_length=1)
    language: str = "Spanish"
    genre: str
    tone: str
    narrative_profile: NarrativeProfile
    premise: str
    constraints: list[str] = Field(default_factory=list)
    creative_directions: list[str] = Field(default_factory=list)

    def agent_spec(self) -> dict:
        """Return trusted downstream data without replaying the raw prompt."""
        return self.model_dump(mode="json", exclude={"original_prompt"})


class Location(BaseModel):
    """Represent Location data and behavior."""

    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class StoryObject(BaseModel):
    """Represent StoryObject data and behavior."""

    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class WorldArtifact(BaseModel):
    """Represent WorldArtifact data and behavior."""

    setting: str
    time_period: str
    rules: list[str] = Field(min_length=1)
    locations: list[Location] = Field(min_length=1)
    objects: list[StoryObject] = Field(default_factory=list)
    atmosphere: str

    @model_validator(mode="after")
    def ids_are_unique(self) -> WorldArtifact:
        """Handle the ids are unique operation for WorldArtifact."""
        location_ids = [item.id for item in self.locations]
        object_ids = [item.id for item in self.objects]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("world location ids must be unique")
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("world object ids must be unique")
        return self


class CharacterProfile(BaseModel):
    """Represent CharacterProfile data and behavior."""

    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    role: str
    goal: str
    motivation: str
    conflict: str
    arc: str
    voice: str


class CharacterRelationship(BaseModel):
    """Represent CharacterRelationship data and behavior."""

    source_character_id: str = Field(pattern=ID_PATTERN)
    target_character_id: str = Field(pattern=ID_PATTERN)
    description: str = Field(min_length=1)


class CharactersArtifact(BaseModel):
    """Represent CharactersArtifact data and behavior."""

    characters: list[CharacterProfile] = Field(min_length=1)
    relationships: list[CharacterRelationship] = Field(default_factory=list)

    @model_validator(mode="after")
    def references_are_valid(self) -> CharactersArtifact:
        """Handle the references are valid operation for CharactersArtifact."""
        ids = [item.id for item in self.characters]
        names = [item.name.casefold().strip() for item in self.characters]
        if len(ids) != len(set(ids)) or len(names) != len(set(names)):
            raise ValueError("character ids and names must be unique")
        known = set(ids)
        for relationship in self.relationships:
            refs = {
                relationship.source_character_id,
                relationship.target_character_id,
            }
            if refs - known:
                raise ValueError("character relationships reference unknown characters")
            if len(refs) != 2:
                raise ValueError("character relationships cannot be self-referential")
        return self


class ChapterDraft(BaseModel):
    """Represent ChapterDraft data and behavior."""

    id: str = Field(pattern=ID_PATTERN)
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    dramatic_goal: str = Field(min_length=1)
    opening_state: str = Field(min_length=1)
    turning_point: str = Field(min_length=1)
    closing_state: str = Field(min_length=1)


class ChapterPlan(ChapterDraft):
    """Represent ChapterPlan data and behavior."""


class PlotEvent(BaseModel):
    """Represent PlotEvent data and behavior."""

    id: str = Field(pattern=ID_PATTERN)
    order: int = Field(ge=1)
    chapter_id: str = Field(pattern=ID_PATTERN)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    dramatic_function: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    preconditions: list[str] = Field(
        default_factory=list,
        description="Plain-English story-state conditions, not entity or event IDs.",
    )
    character_ids: list[str] = Field(default_factory=list)
    location_id: str | None = None
    object_ids: list[str] = Field(
        default_factory=list,
        description="Canonical StoryObject IDs used in this event.",
    )
    effects: list[str] = Field(
        min_length=1,
        description="Plain-English story-state changes caused by this event, not IDs.",
    )
    payoff_of: list[str] = Field(
        default_factory=list,
        description=(
            "PlotEvent IDs for setups paid off by this event. Every value must be the ID "
            "of an earlier event; never use object, character, location, or prose values. "
            "Use an empty list when this event pays off no earlier event."
        ),
    )


class EventDependency(BaseModel):
    """Represent EventDependency data and behavior."""

    source_event_id: str = Field(pattern=ID_PATTERN)
    target_event_id: str = Field(pattern=ID_PATTERN)
    relation: Literal["causal", "temporal"]


class StoryPlanDraft(BaseModel):
    """Represent StoryPlanDraft data and behavior."""

    logline: str
    theme: str
    ending: str
    narrative_structure: str = Field(min_length=1)
    dramatic_question: str = Field(min_length=1)
    stakes: str = Field(min_length=1)
    chapters: list[ChapterDraft] = Field(min_length=1)
    events: list[PlotEvent] = Field(min_length=1)
    dependencies: list[EventDependency] = Field(default_factory=list)


class StoryPlan(BaseModel):
    """Represent StoryPlan data and behavior."""

    logline: str
    theme: str
    ending: str
    narrative_structure: str = Field(min_length=1)
    dramatic_question: str = Field(min_length=1)
    stakes: str = Field(min_length=1)
    chapters: list[ChapterPlan] = Field(min_length=1)
    events: list[PlotEvent] = Field(min_length=1)
    dependencies: list[EventDependency] = Field(default_factory=list)
    topological_order: list[str] = Field(default_factory=list)


class ConstraintCheck(BaseModel):
    """Represent ConstraintCheck data and behavior."""

    constraint: str
    passed: bool
    notes: str = ""


class RevisionNote(BaseModel):
    """One actionable English-language instruction for plan or prose revision."""

    id: str = Field(pattern=ID_PATTERN)
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


class ChapterPresentation(BaseModel):
    """Localized public title for one internally planned chapter."""

    chapter_id: str = Field(pattern=ID_PATTERN)
    title: str = Field(min_length=1)


class StoryPresentation(BaseModel):
    """Localized titles created when the drafting phase begins."""

    title: str = Field(min_length=1)
    chapters: list[ChapterPresentation] = Field(min_length=1)

    @model_validator(mode="after")
    def chapter_ids_are_unique(self) -> StoryPresentation:
        """Require one unambiguous localized title per chapter."""
        identifiers = [item.chapter_id for item in self.chapters]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("presentation chapter ids must be unique")
        return self


class StoryReview(BaseModel):
    """Represent StoryReview data and behavior."""

    strengths: list[str] = Field(default_factory=list)
    notes: list[RevisionNote] = Field(default_factory=list)
    constraint_checks: list[ConstraintCheck] = Field(default_factory=list)


class ChapterMetrics(BaseModel):
    """Record observed chapter size without defining a target."""

    chapter_id: str = Field(pattern=ID_PATTERN)
    words: int = Field(ge=0)
    events: int = Field(ge=0)


class StoryMetrics(BaseModel):
    """Record observed story characteristics without budget compliance."""

    narrative_profile: NarrativeProfile
    words: int = Field(ge=0)
    chapters: int = Field(ge=0)
    events: int = Field(ge=0)
    chapter_metrics: list[ChapterMetrics] = Field(default_factory=list)


class WriterCandidateDiagnostic(BaseModel):
    """Explain why one Writer candidate was rejected and how to correct it."""

    code: Literal[
        "EMPTY_CHAPTER_BODY",
        "MARKDOWN_HEADINGS",
        "UNCHANGED_SIGNIFICANT_NOTES",
    ]
    message: str
    retry_instruction: str
    actual_words: int


class ChapterRevisionAttempt(BaseModel):
    """Record the auditable outcome of one bounded Writer call."""

    attempt: int = Field(ge=1)
    status: Literal["accepted", "rejected", "failed"]
    artifact: str | None = None
    diagnostic: WriterCandidateDiagnostic | None = None
    exception_type: str | None = None


class ChapterRevisionResult(BaseModel):
    """Summarize every Writer attempt and the chapter body ultimately delivered."""

    chapter_id: str = Field(pattern=ID_PATTERN)
    chapter_index: int = Field(ge=1)
    note_ids: list[str] = Field(default_factory=list)
    draft_words: int
    attempts: list[ChapterRevisionAttempt] = Field(default_factory=list)
    final_source: Literal["revision", "draft"]
    final_words: int
    warning_code: Literal["WRITER_REVISION_REJECTED"] | None = None


class RevisionReport(BaseModel):
    """Persist the complete chapter-level Writer decision trail."""

    chapters: list[ChapterRevisionResult] = Field(default_factory=list)


class ErrorReport(BaseModel):
    """Represent ErrorReport data and behavior."""

    code: str
    stage: str
    run_id: str
    summary: str
    details: dict = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class GeneratorVersionArtifact(BaseModel):
    """Identify the generator release and artifact contract used by one run."""

    generator: str = GENERATOR_NAME
    generator_version: str = Field(default=GENERATOR_VERSION, pattern=r"^\d+\.\d+\.\d+$")
    pipeline_version: str = Field(default=PIPELINE_VERSION, pattern=r"^\d+\.\d+$")


class LLMUsageRecord(BaseModel):
    """Represent LLMUsageRecord data and behavior."""

    call_id: str
    operation: str
    stage: str
    attempt: int
    status: Literal["succeeded", "failed"]
    model: str
    timestamp: datetime
    duration_seconds: float = 0
    prompt_tokens: int = 0
    candidate_tokens: int = 0
    thoughts_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    retries: int = 0
    wait_seconds: float = 0
    error_code: str | None = None


class LLMUsageArtifact(BaseModel):
    """Represent LLMUsageArtifact data and behavior."""

    records: list[LLMUsageRecord] = Field(default_factory=list)
    calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_wait_seconds: float = 0


class RunMetadata(BaseModel):
    """Represent RunMetadata data and behavior."""

    run_id: str
    model: str
    created_at: datetime
    updated_at: datetime
    status: Literal["running", "completed", "failed"]
    completed_stages: list[str] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    error_stage: str | None = None
    warnings: list[str] = Field(default_factory=list)
    pipeline_version: str = PIPELINE_VERSION
