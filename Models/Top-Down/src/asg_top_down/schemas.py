"""Validated contracts exchanged by the Top-Down v2 pipeline."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StoryRequest(BaseModel):
    original_prompt: str
    title: str = Field(description="Short proposed story title")
    language: str = "español"
    genre: str
    tone: str
    target_words: int = Field(default=1500, ge=300, le=20_000)
    premise: str
    constraints: list[str] = Field(default_factory=list)


class ArchetypeSelection(BaseModel):
    primary: str
    secondary: list[str] = Field(default_factory=list, max_length=2)
    confidence: float = Field(ge=0, le=1)
    prompt_evidence: list[str] = Field(default_factory=list)
    rationale: str

    @model_validator(mode="after")
    def unique_archetypes(self) -> "ArchetypeSelection":
        chosen = [self.primary, *self.secondary]
        if len(chosen) != len(set(chosen)):
            raise ValueError("primary and secondary archetypes must be unique")
        return self


class StoryPlanArtifact(BaseModel):
    logline: str
    theme: str
    central_conflict: str
    progression: list[str] = Field(min_length=3)
    intended_ending: str
    archetypes: ArchetypeSelection


class WorldArtifact(BaseModel):
    setting: str
    time_period: str
    rules: list[str]
    locations: list[str]
    atmosphere: str


class Character(BaseModel):
    name: str
    narrative_role: str
    jungian_archetype: str
    goal: str
    motivation: str
    conflict: str
    arc: str


class CharactersArtifact(BaseModel):
    characters: list[Character] = Field(min_length=1)
    relationships: list[str] = Field(default_factory=list)


class StoryBeat(BaseModel):
    id: str
    scene_id: str
    global_order: int = Field(ge=1)
    local_order: int = Field(ge=1)
    beat_type: str
    objective: str
    conflict: str
    action: str
    outcome: str
    participants: list[str]
    emotional_shift: str
    setup_refs: list[str] = Field(default_factory=list)
    payoff_refs: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    id: str
    order: int = Field(ge=1)
    title: str
    purpose: str
    point_of_view: str
    location: str
    characters: list[str]
    target_words: int = Field(ge=50)
    entry_state: str
    exit_state: str
    beat_ids: list[str] = Field(min_length=1)


EdgeType = Literal["causes", "enables", "motivates", "reveals", "setup_payoff"]


class CausalEdge(BaseModel):
    source: str
    target: str
    relation: EdgeType
    strength: int = Field(ge=1, le=5)
    rationale: str


class DirectedStoryArtifact(BaseModel):
    scenes: list[Scene] = Field(min_length=1)
    beats: list[StoryBeat] = Field(min_length=1)
    candidate_edges: list[CausalEdge] = Field(default_factory=list)


class DiscardedEdge(BaseModel):
    edge: CausalEdge
    reason: Literal["would_create_cycle"]


class NarrativeGraphArtifact(BaseModel):
    scenes: list[Scene]
    beats: list[StoryBeat]
    candidate_edges: list[CausalEdge]
    accepted_edges: list[CausalEdge]
    discarded_edges: list[DiscardedEdge]
    topological_order: list[str]


class ReviewArtifact(BaseModel):
    coherence_score: int = Field(ge=1, le=10)
    continuity_score: int = Field(ge=1, le=10)
    style_score: int = Field(ge=1, le=10)
    compliance_score: int = Field(ge=1, le=10)
    archetype_score: int = Field(ge=1, le=10)
    graph_coverage_score: int = Field(ge=1, le=10)
    strengths: list[str]
    issues: list[str]
    revision_instructions: list[str]


class RunMetadata(BaseModel):
    run_id: str
    model: str
    created_at: datetime
    updated_at: datetime
    status: Literal["running", "completed", "failed"]
    completed_stages: list[str] = Field(default_factory=list)
    error: str | None = None
