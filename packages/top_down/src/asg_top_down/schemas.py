"""Data contracts for the small Top-Down 5.0 pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class StoryRequest(BaseModel):
    """Represent StoryRequest data and behavior."""

    original_prompt: str
    processed_prompt: str = ""
    title: str = Field(min_length=1)
    language: str = "Spanish"
    genre: str
    tone: str
    target_words: int = Field(default=1500, ge=300, le=20_000)
    requested_chapters: int | None = Field(default=None, ge=1, le=80)
    premise: str
    constraints: list[str] = Field(default_factory=list)

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


class ChapterPlan(ChapterDraft):
    """Represent ChapterPlan data and behavior."""

    target_words: int = Field(ge=200)


class PlotEvent(BaseModel):
    """Represent PlotEvent data and behavior."""

    id: str = Field(pattern=ID_PATTERN)
    order: int = Field(ge=1)
    chapter_id: str = Field(pattern=ID_PATTERN)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    character_ids: list[str] = Field(default_factory=list)
    location_id: str | None = None
    object_ids: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)


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
    chapters: list[ChapterDraft] = Field(min_length=1)
    events: list[PlotEvent] = Field(min_length=1)
    dependencies: list[EventDependency] = Field(default_factory=list)


class StoryPlan(BaseModel):
    """Represent StoryPlan data and behavior."""

    logline: str
    theme: str
    ending: str
    chapters: list[ChapterPlan] = Field(min_length=1)
    events: list[PlotEvent] = Field(min_length=1)
    dependencies: list[EventDependency] = Field(default_factory=list)
    topological_order: list[str] = Field(default_factory=list)


class ConstraintCheck(BaseModel):
    """Represent ConstraintCheck data and behavior."""

    constraint: str
    passed: bool
    notes: str = ""


class StoryReview(BaseModel):
    """Represent StoryReview data and behavior."""

    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    constraint_checks: list[ConstraintCheck] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)


class LengthAuditEntry(BaseModel):
    """Represent LengthAuditEntry data and behavior."""

    target_words: int
    minimum_words: int
    maximum_words: int
    actual_words: int
    within_tolerance: bool


class ChapterLengthAudit(LengthAuditEntry):
    """Represent ChapterLengthAudit data and behavior."""

    chapter_id: str


class LengthAuditArtifact(BaseModel):
    """Represent LengthAuditArtifact data and behavior."""

    chapters: list[ChapterLengthAudit]
    total: LengthAuditEntry


class ErrorReport(BaseModel):
    """Represent ErrorReport data and behavior."""

    code: str
    stage: str
    run_id: str
    summary: str
    details: dict = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


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
    pipeline_version: str = "5.0"
