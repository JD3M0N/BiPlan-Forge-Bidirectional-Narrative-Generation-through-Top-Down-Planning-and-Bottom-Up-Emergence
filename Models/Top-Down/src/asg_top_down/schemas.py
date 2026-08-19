"""Validated contracts exchanged by the production STORYTELLER pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class StoryRequest(BaseModel):
    original_prompt: str
    processed_prompt: str = Field(
        default="",
        description="Self-contained English enrichment of the user's request",
    )
    title: str = Field(description="Short proposed story title")
    language: str = Field(
        default="Spanish",
        description="English name of the required fiction output language",
    )
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


class TaxonomyOptionReference(BaseModel):
    """Reference to one option owned by a retrieved taxonomy profile."""

    taxonomy_id: str = Field(min_length=1)
    option_id: str = Field(min_length=1)


class TaxonomyApplication(BaseModel):
    """Story-specific, deliberately partial use of the taxonomy palette."""

    primary_taxonomy_id: str = Field(min_length=1)
    accent_taxonomy_id: str | None = None
    selected_promises: list[TaxonomyOptionReference] = Field(min_length=1, max_length=3)
    selected_roles: list[TaxonomyOptionReference] = Field(default_factory=list, max_length=6)
    selected_movements: list[TaxonomyOptionReference] = Field(min_length=2, max_length=7)
    selected_complications: list[TaxonomyOptionReference] = Field(default_factory=list, max_length=2)
    selected_twist: TaxonomyOptionReference | None = None
    selected_conclusion: TaxonomyOptionReference
    omitted_conventions: list[TaxonomyOptionReference] = Field(default_factory=list, max_length=8)
    freshness_choices: list[str] = Field(default_factory=list, min_length=1, max_length=4)
    prompt_evidence: list[str] = Field(default_factory=list, min_length=1)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def primary_and_accent_are_distinct(self) -> "TaxonomyApplication":
        if self.accent_taxonomy_id == self.primary_taxonomy_id:
            raise ValueError("accent taxonomy must differ from the primary taxonomy")
        allowed = {self.primary_taxonomy_id}
        if self.accent_taxonomy_id:
            allowed.add(self.accent_taxonomy_id)
        references = [
            *self.selected_promises, *self.selected_roles, *self.selected_movements,
            *self.selected_complications, self.selected_conclusion,
            *self.omitted_conventions,
        ]
        if self.selected_twist:
            references.append(self.selected_twist)
        unknown = {item.taxonomy_id for item in references} - allowed
        if unknown:
            raise ValueError("taxonomy options may only come from the primary or accent taxonomy")
        return self


class TaxonomyBrief(BaseModel):
    """Compact English guidance compiled from a validated taxonomy application."""

    primary_taxonomy: str
    accent_taxonomy: str | None = None
    reader_promises: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    movements: list[str] = Field(default_factory=list)
    complications: list[str] = Field(default_factory=list)
    twist: str | None = None
    conclusion: str | None = None
    freshness_choices: list[str] = Field(default_factory=list)
    quality_checks: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    usage_rule: str = (
        "Use this material as a flexible palette. Preserve the reader promises selected for this "
        "story, but freely merge, omit, reorder, or reinterpret non-core conventions."
    )


class StoryPlanArtifact(BaseModel):
    logline: str
    theme: str
    central_conflict: str
    progression: list[str] = Field(min_length=3)
    intended_ending: str
    taxonomy_application: TaxonomyApplication | None = None
    archetypes: ArchetypeSelection | None = None

    @model_validator(mode="after")
    def has_planning_framework(self) -> "StoryPlanArtifact":
        if self.taxonomy_application is None and self.archetypes is None:
            raise ValueError("story plan requires taxonomy_application")
        return self


class WorldArtifact(BaseModel):
    setting: str
    time_period: str
    rules: list[str]
    locations: list[str]
    atmosphere: str


SliderName = Literal["sympathy", "competence", "proactivity"]


class SliderRange(BaseModel):
    start: int = Field(ge=1, le=10)
    target: int = Field(ge=1, le=10)
    rationale: str = Field(min_length=1)


class CharacterSliderArc(BaseModel):
    sympathy: SliderRange
    competence: SliderRange
    proactivity: SliderRange
    focus: SliderName
    direction: Literal["ascending"] = "ascending"
    justification: str = Field(min_length=1)

    @model_validator(mode="after")
    def two_high_one_growing_low(self) -> "CharacterSliderArc":
        ranges = {
            "sympathy": self.sympathy,
            "competence": self.competence,
            "proactivity": self.proactivity,
        }
        high = [name for name, value in ranges.items() if 7 <= value.start <= 10]
        low = [name for name, value in ranges.items() if 1 <= value.start <= 4]
        if len(high) != 2 or len(low) != 1:
            raise ValueError("main-character sliders require exactly two high starts and one low start")
        if self.focus != low[0]:
            raise ValueError("the low starting slider must be the focus")
        focused = ranges[self.focus]
        if focused.target < 7 or focused.target <= focused.start:
            raise ValueError("the focus slider must grow from low to high")
        if any(ranges[name].target < 7 for name in high):
            raise ValueError("the two high sliders must remain high")
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


FreytagPhase = Literal["exposition", "rising_action", "climax", "falling_action", "denouement"]
NodeType = Literal["CBN", "CPN", "CEN"]
EdgeType = Literal["causes", "enables", "motivates", "reveals"]
TryFailOutcome = Literal["yes_but", "no_and"]
ReviewFocus = Literal[
    "theme", "logic", "emotion", "mystery", "plot_resolution", "language", "redundancy",
]


class NodeGoal(BaseModel):
    purpose: str
    taxonomy_id: str | None = None
    taxonomy_movement_id: str | None = None
    archetype_id: str | None = None
    schema_beat_id: str | None = None
    success_criteria: list[str] = Field(min_length=1)


class ChapterPlan(BaseModel):
    id: str
    order: int = Field(ge=1)
    title: str
    abstract: str
    target_words: int = Field(ge=50)
    freytag_phases: list[FreytagPhase] = Field(min_length=1)


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

    @model_validator(mode="after")
    def normalize_sv(self) -> "PlotNode":
        if not self.object.strip():
            self.object = self.subject
        return self


class EntityStateChange(BaseModel):
    entity: str
    attribute: Literal["location", "possession", "knowledge", "situation", "relationship"]
    value: str


class PlotNodeProposal(BaseModel):
    subject: str = Field(min_length=1)
    verb: str = Field(min_length=1)
    object: str = ""
    purpose: str = Field(min_length=1)
    taxonomy_id: str | None = None
    taxonomy_movement_id: str | None = None
    schema_beat_id: str | None = None
    preconditions: list[str] = Field(min_length=1)
    effects: list[str] = Field(min_length=1)
    intention: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    state_changes: list[EntityStateChange] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_sv(self) -> "PlotNodeProposal":
        if not self.object.strip():
            self.object = self.subject
        return self


class PlotNodeReview(BaseModel):
    """Semantic review of the final candidate, including a possible full replacement."""

    accepted: bool
    causal: bool
    intentional: bool
    conflict_present: bool
    continuous: bool
    novel: bool
    advances_ending: bool
    world_consistent: bool
    aligns_with_cen: bool = False
    review_focus: list[ReviewFocus] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    revised: PlotNodeProposal | None = None

    @model_validator(mode="after")
    def acceptance_is_earned(self) -> "PlotNodeReview":
        checks = (
            "causal", "intentional", "conflict_present", "continuous",
            "novel", "advances_ending", "world_consistent",
        )
        failed = [name for name in checks if not getattr(self, name)]
        if self.accepted and failed:
            self.accepted = False
            self.issues.append("Failed review checks: " + ", ".join(failed))
        elif not self.accepted and not self.issues:
            self.issues.append("The reviewer rejected the candidate without an actionable issue")
        return self


class AcceptedNodeRecord(BaseModel):
    node: PlotNode
    state_changes: list[EntityStateChange] = Field(default_factory=list)
    review: PlotNodeReview
    attempt: int = Field(ge=1)


class NarrativeEdge(BaseModel):
    source: str
    target: str
    relation: EdgeType
    strength: int = Field(ge=1, le=5)
    rationale: str


class IncrementalStorylineArtifact(BaseModel):
    chapters: list[ChapterPlan]
    nodes: list[PlotNode]
    accepted_edges: list[NarrativeEdge]
    topological_order: list[str]


class NarrativeEntity(BaseModel):
    id: str
    name: str
    state: dict[str, str] = Field(default_factory=dict)
    last_event_id: str | None = None


class EntityRelation(BaseModel):
    source: str
    verb: str
    target: str
    plot_node_id: str
    timestamp: int


class NarrativeEntityGraphArtifact(BaseModel):
    entities: list[NarrativeEntity] = Field(default_factory=list)
    relations: list[EntityRelation] = Field(default_factory=list)


PPPLineKind = Literal["plot", "character", "relationship"]
PPPPhase = Literal["promise", "progress", "payoff"]


class TonePromise(BaseModel):
    description: str = Field(min_length=1)
    opening_signal: str = Field(min_length=1)
    continuity_rule: str = Field(min_length=1)


class GlobalPPPPoint(BaseModel):
    id: str = Field(min_length=1)
    chapter_id: str
    description: str = Field(min_length=1)
    reader_effect: str = Field(min_length=1)


class GlobalPPPLine(BaseModel):
    id: str = Field(min_length=1)
    kind: PPPLineKind
    subject: str = Field(min_length=1)
    promise: GlobalPPPPoint
    progress: list[GlobalPPPPoint] = Field(min_length=1)
    payoff: GlobalPPPPoint

    @model_validator(mode="after")
    def point_ids_are_unique(self) -> "GlobalPPPLine":
        ids = [self.promise.id, *(point.id for point in self.progress), self.payoff.id]
        if len(ids) != len(set(ids)):
            raise ValueError("global PPP point ids must be unique within a line")
        return self


class GlobalPPPPlan(BaseModel):
    tone_promise: TonePromise
    primary_line: GlobalPPPLine
    secondary_lines: list[GlobalPPPLine] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def line_and_point_ids_are_unique(self) -> "GlobalPPPPlan":
        lines = [self.primary_line, *self.secondary_lines]
        line_ids = [line.id for line in lines]
        point_ids = [point.id for line in lines
                     for point in [line.promise, *line.progress, line.payoff]]
        if len(line_ids) != len(set(line_ids)):
            raise ValueError("global PPP line ids must be unique")
        if len(point_ids) != len(set(point_ids)):
            raise ValueError("global PPP point ids must be unique")
        return self


class CharacterMilestone(BaseModel):
    character_name: str = Field(min_length=1)
    chapter_id: str
    stage: Literal["start", "transition", "end"]
    description: str = Field(min_length=1)


class CharacterArcPlan(BaseModel):
    milestones: list[CharacterMilestone] = Field(min_length=1)


class TryFailCycle(BaseModel):
    id: str = Field(min_length=1)
    chapter_id: str
    action: str = Field(min_length=1)
    outcome: TryFailOutcome
    consequence: str = Field(min_length=1)


class TryFailPlan(BaseModel):
    cycles: list[TryFailCycle] = Field(min_length=1)


class StorylineObligation(BaseModel):
    id: str = Field(min_length=1)
    chapter_id: str
    source: Literal["global_ppp", "character_arc", "try_fail"]
    phase: str = Field(min_length=1)
    description: str = Field(min_length=1)


class StorylineObligationsArtifact(BaseModel):
    obligations: list[StorylineObligation] = Field(min_length=1)


class ChapterPPPBeat(BaseModel):
    description: str = Field(min_length=1)
    node_ids: list[str] = Field(min_length=1)


class ChapterPPPPlan(BaseModel):
    chapter_id: str
    promise: ChapterPPPBeat
    progress: list[ChapterPPPBeat] = Field(min_length=1)
    payoff: ChapterPPPBeat
    advances_global_point_ids: list[str] = Field(min_length=1)


class PPPLineBrief(BaseModel):
    kind: PPPLineKind
    subject: str
    promise: str
    progress: list[str]
    payoff: str


class ChapterWritingBrief(BaseModel):
    tone_promise: str
    global_lines: list[PPPLineBrief] = Field(min_length=1)
    chapter_promise: str
    chapter_progress: list[str] = Field(min_length=1)
    chapter_payoff: str
    character_milestones: list[str] = Field(default_factory=list)
    try_fail_cycles: list[str] = Field(default_factory=list)


class ObligationTraceEntry(BaseModel):
    obligation_id: str
    chapter_id: str
    node_ids: list[str] = Field(min_length=1)


class StorylineObligationTrace(BaseModel):
    entries: list[ObligationTraceEntry] = Field(min_length=1)


class StoryCraftPlan(BaseModel):
    global_ppp: GlobalPPPPlan
    character_arcs: CharacterArcPlan
    try_fail: TryFailPlan
    chapters: list[ChapterPPPPlan] = Field(min_length=1)


class DiagnosticAudit(BaseModel):
    causal_issues: list[str] = Field(default_factory=list)
    intentionality_issues: list[str] = Field(default_factory=list)
    continuity_issues: list[str] = Field(default_factory=list)
    template_like_passages: list[str] = Field(default_factory=list)
    revision_suggestions: list[str] = Field(default_factory=list)


AuditVerdict = Literal["pass", "fail", "not_applicable"]


class CraftAuditAnswer(BaseModel):
    question_id: str
    category: Literal[
        "global_ppp", "chapter_ppp", "character", "try_fail", "constraint", "taxonomy",
        "language", "global",
    ]
    subject_id: str
    question: str
    blocking: bool = True
    verdict: AuditVerdict
    evidence: str
    issue: str = ""
    revision_instruction: str = ""

    @model_validator(mode="after")
    def failures_are_actionable(self) -> "CraftAuditAnswer":
        if self.verdict == "fail" and (not self.issue.strip() or not self.revision_instruction.strip()):
            raise ValueError("failed audit answers require an issue and revision instruction")
        return self


class CraftAuditArtifact(BaseModel):
    answers: list[CraftAuditAnswer]
    summary: str

    @property
    def failed_blocking_ids(self) -> list[str]:
        return [answer.question_id for answer in self.answers
                if answer.blocking and answer.verdict == "fail"]

    @property
    def passed(self) -> bool:
        return not self.failed_blocking_ids

    @property
    def revision_instructions(self) -> list[str]:
        return [answer.revision_instruction for answer in self.answers if answer.verdict == "fail"]


class CraftRevisionAttempt(BaseModel):
    attempt: int = Field(ge=0)
    text_file: str
    audit_file: str
    passed: bool
    failed_blocking_ids: list[str] = Field(default_factory=list)
    failed_advisory_ids: list[str] = Field(default_factory=list)


class CraftRevisionHistory(BaseModel):
    selected_attempt: int = Field(ge=0)
    exhausted: bool
    attempts: list[CraftRevisionAttempt] = Field(default_factory=list)


class LengthAuditEntry(BaseModel):
    target_words: int
    minimum_words: int
    maximum_words: int
    actual_words: int
    within_tolerance: bool


class LengthAuditArtifact(BaseModel):
    chapters: list[LengthAuditEntry] = Field(default_factory=list)
    total: LengthAuditEntry


class ErrorReport(BaseModel):
    code: str
    stage: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class LLMUsageRecord(BaseModel):
    operation: str
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
    total_tokens: int = 0
    total_wait_seconds: float = 0


class RunMetadata(BaseModel):
    run_id: str
    model: str
    created_at: datetime
    updated_at: datetime
    status: Literal["running", "completed", "failed"] = "running"
    completed_stages: list[str] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    error_stage: str | None = None
    warnings: list[str] = Field(default_factory=list)
    pipeline_version: str = "3.3"
