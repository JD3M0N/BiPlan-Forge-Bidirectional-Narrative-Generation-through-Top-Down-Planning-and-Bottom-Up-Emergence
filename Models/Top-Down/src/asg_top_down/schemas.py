"""Validated contracts exchanged by the STORYTELLER-style pipeline."""

from datetime import datetime
from typing import Any, Literal

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


FreytagPhase = Literal["exposition", "rising_action", "climax", "falling_action", "denouement"]
NodeType = Literal["CBN", "CPN", "CEN"]
EdgeType = Literal["causes", "enables", "motivates", "reveals", "setup_payoff"]


class NodeGoal(BaseModel):
    purpose: str
    archetype_id: str
    taxonomy_beat: str
    success_criteria: list[str] = Field(min_length=1)


class ChapterPlan(BaseModel):
    id: str
    order: int = Field(ge=1)
    title: str
    abstract: str
    target_words: int = Field(ge=50)
    freytag_phases: list[FreytagPhase] = Field(min_length=1)


class PlotNode(BaseModel):
    id: str
    chapter_id: str
    node_type: NodeType
    subject: str = Field(min_length=1)
    verb: str = Field(min_length=1)
    object: str = ""
    timestamp: int = Field(ge=0)
    global_order: int = Field(ge=1)
    local_order: int = Field(ge=1)
    target_words: int = Field(ge=1)
    goals: list[NodeGoal] = Field(min_length=1)

    @model_validator(mode="after")
    def normalize_sv(self) -> "PlotNode":
        if not self.object.strip():
            self.object = self.subject
        return self


class NarrativeEdge(BaseModel):
    source: str
    target: str
    relation: EdgeType
    strength: int = Field(default=3, ge=1, le=5)
    rationale: str


class DirectedStoryArtifact(BaseModel):
    """Candidate storyline emitted by the Director."""
    chapters: list[ChapterPlan] = Field(min_length=1)
    nodes: list[PlotNode] = Field(min_length=3)
    candidate_edges: list[NarrativeEdge] = Field(min_length=1)


class DiscardedEdge(BaseModel):
    edge: NarrativeEdge
    reason: Literal["would_create_cycle"]


class StorylineArtifact(BaseModel):
    chapters: list[ChapterPlan]
    nodes: list[PlotNode]
    candidate_edges: list[NarrativeEdge]
    accepted_edges: list[NarrativeEdge]
    discarded_edges: list[DiscardedEdge] = Field(default_factory=list)
    topological_order: list[str]


# Backwards-compatible public name used by console integrations.
NarrativeGraphArtifact = StorylineArtifact


class NarrativeEntity(BaseModel):
    id: str
    name: str
    kinds: list[str] = Field(default_factory=list)


class EntityRelation(BaseModel):
    source: str
    verb: str
    target: str
    plot_node_id: str
    timestamp: int = Field(ge=0)


class NarrativeEntityGraphArtifact(BaseModel):
    entities: list[NarrativeEntity]
    relations: list[EntityRelation]


class NodeReview(BaseModel):
    node_id: str
    accepted: bool
    issues: list[str] = Field(default_factory=list)
    explanation: str


class NodeReviewsArtifact(BaseModel):
    reviews: list[NodeReview] = Field(default_factory=list)


class ReplanningAttempt(BaseModel):
    chapter_id: str
    attempt: int = Field(ge=1, le=5)
    diagnostics: list[str]


class ReplanningHistoryArtifact(BaseModel):
    attempts: list[ReplanningAttempt] = Field(default_factory=list)


class FreytagPhaseAssessment(BaseModel):
    phase: FreytagPhase
    present: bool
    chapter_ids: list[str]
    node_ids: list[str]
    intensity: int = Field(ge=1, le=10)
    evidence: str


class FreytagReviewArtifact(BaseModel):
    passed: bool
    phases: list[FreytagPhaseAssessment]
    issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)


class ChapterComplianceArtifact(BaseModel):
    passed: bool
    actual_words: int = Field(ge=0)
    covered_node_ids: list[str] = Field(default_factory=list)
    covered_goals: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)


class ChapterComplianceAttempt(BaseModel):
    chapter_id: str
    chapter_title: str
    attempt: int = Field(ge=1, le=3)
    target_words: int
    actual_words: int
    word_difference: int
    expected_node_ids: list[str]
    covered_node_ids: list[str]
    missing_node_ids: list[str]
    expected_goals: list[str]
    covered_goals: list[str]
    missing_goals: list[str]
    passed: bool
    issues: list[str]
    revision_instructions: list[str]


class ChapterComplianceHistory(BaseModel):
    attempts: list[ChapterComplianceAttempt] = Field(default_factory=list)


class LengthAuditEntry(BaseModel):
    target_words: int = Field(ge=1)
    minimum_words: int = Field(ge=0)
    maximum_words: int = Field(ge=1)
    actual_words: int = Field(ge=0)
    within_tolerance: bool


class ChapterLengthAudit(LengthAuditEntry):
    chapter_id: str
    chapter_title: str


class LengthAuditArtifact(BaseModel):
    chapters: list[ChapterLengthAudit] = Field(default_factory=list)
    total: LengthAuditEntry


class ErrorReport(BaseModel):
    code: str
    stage: str
    run_id: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class LLMUsageRecord(BaseModel):
    operation: str
    model: str
    timestamp: datetime
    duration_seconds: float = Field(ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    candidate_tokens: int = Field(default=0, ge=0)
    thoughts_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    wait_seconds: float = Field(default=0, ge=0)


class LLMUsageArtifact(BaseModel):
    records: list[LLMUsageRecord] = Field(default_factory=list)
    calls: int = 0
    total_tokens: int = 0
    total_wait_seconds: float = 0


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
    error_code: str | None = None
    error_stage: str | None = None
