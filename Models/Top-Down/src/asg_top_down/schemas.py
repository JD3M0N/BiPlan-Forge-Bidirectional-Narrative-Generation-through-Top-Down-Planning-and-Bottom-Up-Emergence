"""Validated contracts exchanged by the production STORYTELLER pipeline."""

from __future__ import annotations

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
    archetype_id: str
    schema_beat_id: str
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
    schema_beat_id: str = Field(min_length=1)
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


PPPLineKind = Literal["master", "plot", "character", "relationship"]


class PPPPoint(BaseModel):
    chapter_id: str
    description: str = Field(min_length=1)


class PPPLine(BaseModel):
    id: str = Field(min_length=1)
    kind: PPPLineKind
    subject: str = Field(min_length=1)
    promise: PPPPoint
    progress: list[PPPPoint] = Field(min_length=1)
    payoff: PPPPoint


class ChapterCraftLine(BaseModel):
    chapter_id: str
    promise: str = Field(min_length=1)
    progress: list[str] = Field(min_length=1)
    payoff: str = Field(min_length=1)
    advances_global_line_ids: list[str] = Field(min_length=1)


class CharacterMilestone(BaseModel):
    character_name: str = Field(min_length=1)
    chapter_id: str
    stage: Literal["start", "transition", "end"]
    description: str = Field(min_length=1)


class TryFailCycle(BaseModel):
    id: str = Field(min_length=1)
    chapter_id: str
    action: str = Field(min_length=1)
    outcome: TryFailOutcome
    consequence: str = Field(min_length=1)


class CraftVariant(BaseModel):
    id: Literal["variant-1", "variant-2", "variant-3"]
    strategy: str = Field(min_length=1)
    master_line: PPPLine
    subplots: list[PPPLine] = Field(default_factory=list, max_length=2)
    chapters: list[ChapterCraftLine] = Field(min_length=1)
    character_milestones: list[CharacterMilestone] = Field(default_factory=list)
    try_fail_cycles: list[TryFailCycle] = Field(default_factory=list)

    @model_validator(mode="after")
    def master_is_master(self) -> "CraftVariant":
        if self.master_line.kind != "master":
            raise ValueError("master_line.kind must be master")
        ids = [self.master_line.id, *(line.id for line in self.subplots)]
        if len(ids) != len(set(ids)):
            raise ValueError("global craft line ids must be unique")
        return self


class CraftVariantsArtifact(BaseModel):
    variants: list[CraftVariant] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def exact_variant_ids(self) -> "CraftVariantsArtifact":
        if {variant.id for variant in self.variants} != {"variant-1", "variant-2", "variant-3"}:
            raise ValueError("craft variants must use variant-1, variant-2, and variant-3")
        return self


class CraftSelectionArtifact(BaseModel):
    selected_variant_id: Literal["variant-1", "variant-2", "variant-3"]
    rationale: str = Field(min_length=1)


class DiagnosticAudit(BaseModel):
    causal_issues: list[str] = Field(default_factory=list)
    intentionality_issues: list[str] = Field(default_factory=list)
    continuity_issues: list[str] = Field(default_factory=list)
    template_like_passages: list[str] = Field(default_factory=list)
    revision_suggestions: list[str] = Field(default_factory=list)


AuditVerdict = Literal["pass", "fail", "not_applicable"]


class CraftAuditAnswer(BaseModel):
    question_id: str
    category: Literal["global_ppp", "chapter_ppp", "character", "try_fail", "constraint", "global"]
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
