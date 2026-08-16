"""Validated contracts exchanged by the STORYTELLER-style pipeline."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, model_validator


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


SliderName = Literal["sympathy", "competence", "proactivity"]
ArcDirection = Literal["ascending", "descending"]


class SliderRange(BaseModel):
    start: int = Field(ge=1, le=10)
    target: int = Field(ge=1, le=10)
    rationale: str = Field(min_length=1)


class CharacterSliderArc(BaseModel):
    sympathy: SliderRange
    competence: SliderRange
    proactivity: SliderRange
    focus: SliderName
    direction: ArcDirection
    justification: str = Field(min_length=1)

    @model_validator(mode="after")
    def focus_matches_direction(self) -> "CharacterSliderArc":
        selected = getattr(self, self.focus)
        if selected.start == selected.target:
            raise ValueError("the focus slider must change")
        if self.direction == "ascending" and selected.target < selected.start:
            raise ValueError("an ascending focus slider must increase")
        if self.direction == "descending" and selected.target > selected.start:
            raise ValueError("a descending focus slider must decrease")
        return self


class Character(BaseModel):
    name: str
    narrative_role: str
    jungian_archetype: str
    goal: str
    motivation: str
    conflict: str
    arc: str
    importance: Literal["main", "supporting"] = "supporting"
    slider_arc: CharacterSliderArc | None = None


class CharactersArtifact(BaseModel):
    characters: list[Character] = Field(min_length=1)
    relationships: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def character_names_are_unique(self) -> "CharactersArtifact":
        names = [character.name.casefold().strip() for character in self.characters]
        if len(names) != len(set(names)):
            raise ValueError("character names must be unique")
        return self


PromiseKind = Literal["tone", "plot", "character"]
CraftBeatKind = Literal["setup", "progress", "payoff"]
TryFailOutcome = Literal["yes_but", "no_and"]
MilestoneStage = Literal["start", "transition", "end"]


class CraftPromise(BaseModel):
    id: str = Field(min_length=1)
    kind: PromiseKind
    character_name: str | None = None
    statement: str = Field(min_length=1)
    setup: str = Field(min_length=1)
    progress_signals: list[str] = Field(min_length=1)
    payoff: str = Field(min_length=1)

    @model_validator(mode="after")
    def character_link_matches_kind(self) -> "CraftPromise":
        if self.kind == "character" and not self.character_name:
            raise ValueError("character promises require character_name")
        if self.kind != "character" and self.character_name is not None:
            raise ValueError("only character promises may reference a character")
        return self


class CraftContractArtifact(BaseModel):
    promises: list[CraftPromise] = Field(min_length=3)
    try_fail_target: int = Field(ge=2, le=7)

    @model_validator(mode="after")
    def core_promises_are_present(self) -> "CraftContractArtifact":
        identifiers = [promise.id for promise in self.promises]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("craft promise ids must be unique")
        if sum(promise.kind == "tone" for promise in self.promises) != 1:
            raise ValueError("the craft contract requires exactly one tone promise")
        if sum(promise.kind == "plot" for promise in self.promises) != 1:
            raise ValueError("the craft contract requires exactly one plot promise")
        if not any(promise.kind == "character" for promise in self.promises):
            raise ValueError("the craft contract requires character promises")
        return self


class CraftBeat(BaseModel):
    id: str = Field(min_length=1)
    promise_id: str = Field(min_length=1)
    kind: CraftBeatKind
    description: str = Field(min_length=1)


class CharacterMilestone(BaseModel):
    id: str = Field(min_length=1)
    character_name: str = Field(min_length=1)
    stage: MilestoneStage
    focus_slider: SliderName
    demonstrated_value: int = Field(ge=1, le=10)
    description: str = Field(min_length=1)


class TryFailCycle(BaseModel):
    id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    outcome: TryFailOutcome
    consequence: str = Field(min_length=1)
    promise_id: str = Field(min_length=1)


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
    craft_beats: list[CraftBeat] = Field(default_factory=list)
    character_milestones: list[CharacterMilestone] = Field(default_factory=list)
    try_fail_cycles: list[TryFailCycle] = Field(default_factory=list)


class StoryOutlineArtifact(BaseModel):
    """High-level STORYTELLER frame produced before any plot node exists."""

    premise: str
    synopsis: str
    chapters: list[ChapterPlan] = Field(min_length=1)


class ChapterAnchors(BaseModel):
    chapter_id: str
    begin_subject: str
    begin_verb: str
    begin_object: str
    end_subject: str
    end_verb: str
    end_object: str


class ChapterAnchorsArtifact(BaseModel):
    anchors: list[ChapterAnchors] = Field(min_length=1)


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
    preconditions: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    intention: str = ""
    conflict: str = ""
    craft_beat_ids: list[str] = Field(default_factory=list)
    character_milestone_ids: list[str] = Field(default_factory=list)
    try_fail_cycle_ids: list[str] = Field(default_factory=list)
    try_fail_outcome: TryFailOutcome | None = None

    @model_validator(mode="after")
    def normalize_sv(self) -> "PlotNode":
        if not self.object.strip():
            self.object = self.subject
        return self


class EntityStateChange(BaseModel):
    entity: str
    attribute: Literal["location", "possession", "knowledge", "status", "relationship"]
    value: str


class PlotNodeProposal(BaseModel):
    subject: str
    verb: str
    object: str
    purpose: str
    schema_beat_id: str
    preconditions: list[str] = Field(min_length=1)
    effects: list[str] = Field(min_length=1)
    intention: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    reaches_chapter_end: bool = False
    state_changes: list[EntityStateChange] = Field(default_factory=list)
    craft_beat_ids: list[str] = Field(default_factory=list)
    character_milestone_ids: list[str] = Field(default_factory=list)
    try_fail_cycle_ids: list[str] = Field(default_factory=list)
    try_fail_outcome: TryFailOutcome | None = None


class PlotNodeReview(BaseModel):
    """Review of the final candidate: ``revised`` when present, otherwise the proposal."""

    accepted: bool = Field(description="Whether the final candidate passes every review check")
    causal: bool
    intentional: bool
    conflict_present: bool
    continuous: bool
    novel: bool
    advances_ending: bool
    world_consistent: bool
    craft_coverage: bool = True
    consequence_persists: bool = True
    try_fail_valid: bool = True
    issues: list[str] = Field(default_factory=list)
    revised: PlotNodeProposal | None = Field(
        default=None,
        description="Complete replacement candidate evaluated by this review",
    )

    @model_validator(mode="after")
    def acceptance_is_earned(self) -> "PlotNodeReview":
        check_names = (
            "causal", "intentional", "conflict_present", "continuous", "novel",
            "advances_ending", "world_consistent", "craft_coverage",
            "consequence_persists", "try_fail_valid",
        )
        failed = [name for name in check_names if not getattr(self, name)]
        if self.accepted and failed:
            self.accepted = False
            issue = "Failed review checks: " + ", ".join(failed)
            if issue not in self.issues:
                self.issues.append(issue)
        elif not self.accepted and not self.issues:
            self.issues.append("The reviewer rejected the node without identifying a failed check")
        return self


class AcceptedNodeRecord(BaseModel):
    node: PlotNode
    state_changes: list[EntityStateChange] = Field(default_factory=list)
    review: PlotNodeReview
    attempt: int = Field(ge=1)


class IncrementalStorylineArtifact(BaseModel):
    chapters: list[ChapterPlan]
    nodes: list[PlotNode]
    accepted_edges: list["NarrativeEdge"]
    topological_order: list[str]


class DiagnosticAudit(BaseModel):
    causal_issues: list[str] = Field(default_factory=list)
    intentionality_issues: list[str] = Field(default_factory=list)
    continuity_issues: list[str] = Field(default_factory=list)
    template_like_passages: list[str] = Field(default_factory=list)
    revision_suggestions: list[str] = Field(default_factory=list)


AuditVerdict = Literal["pass", "fail", "not_applicable"]


class CraftAuditAnswer(BaseModel):
    question_id: str = Field(min_length=1)
    category: Literal["promise", "character", "try_fail", "global"]
    subject_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    verdict: AuditVerdict
    blocking: bool = True
    evidence: str = Field(min_length=1)
    issue: str = ""
    revision_instruction: str = ""

    @model_validator(mode="after")
    def failures_are_actionable(self) -> "CraftAuditAnswer":
        if self.verdict == "fail" and (not self.issue.strip() or not self.revision_instruction.strip()):
            raise ValueError("failed audit answers require an issue and revision instruction")
        return self


class CraftAuditArtifact(BaseModel):
    answers: list[CraftAuditAnswer] = Field(min_length=1)
    summary: str = Field(min_length=1)

    @computed_field(return_type=list[str])
    @property
    def failed_blocking_ids(self) -> list[str]:
        return [answer.question_id for answer in self.answers
                if answer.blocking and answer.verdict != "pass"]

    @computed_field(return_type=bool)
    @property
    def passed(self) -> bool:
        return not self.failed_blocking_ids

    @computed_field(return_type=list[str])
    @property
    def revision_instructions(self) -> list[str]:
        return [answer.revision_instruction for answer in self.answers
                if answer.verdict == "fail" and answer.revision_instruction.strip()]


class CraftRevisionAttempt(BaseModel):
    attempt: int = Field(ge=0)
    text_file: str
    audit_file: str
    passed: bool
    failed_blocking_ids: list[str] = Field(default_factory=list)
    failed_advisory_ids: list[str] = Field(default_factory=list)


class CraftRevisionHistory(BaseModel):
    selected_attempt: int = Field(ge=0)
    exhausted: bool = False
    attempts: list[CraftRevisionAttempt] = Field(min_length=1)


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
    state: dict[str, str] = Field(default_factory=dict)
    last_event_id: str | None = None


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
