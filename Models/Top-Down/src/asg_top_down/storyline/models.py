"""Contracts owned exclusively by the factual STORYLINE subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..domain import ChapterPlan


NodeType = Literal["CBN", "CPN", "CEN"]
EdgeType = Literal["causes", "enables", "motivates", "reveals"]
EntityKind = Literal["character", "location", "object", "concept"]
StateAttribute = Literal["location", "owner", "knowledge", "status", "situation", "relationship"]
PredicateOperator = Literal["equals", "not_equals", "contains", "exists"]
ReviewFocus = Literal[
    "theme", "logic", "emotion", "mystery", "plot_resolution", "language", "redundancy",
]


class EntityRef(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: EntityKind


class StatePredicate(BaseModel):
    entity_id: str
    attribute: StateAttribute
    operator: PredicateOperator = "equals"
    value: str | None = None


class StateMutation(BaseModel):
    entity_id: str
    attribute: StateAttribute
    value: str


class NodeGoal(BaseModel):
    purpose: str
    narrative_function: str | None = None
    taxonomy_id: str | None = None
    taxonomy_movement_id: str | None = None
    success_criteria: list[str] = Field(min_length=1)


class ChapterAnchors(BaseModel):
    chapter_id: str
    begin_location_id: str
    begin_subject: EntityRef
    begin_verb: str
    begin_object: EntityRef
    begin_effects: list[StateMutation] = Field(min_length=1)
    end_location_id: str
    end_subject: EntityRef
    end_verb: str
    end_object: EntityRef
    end_preconditions: list[StatePredicate] = Field(default_factory=list)
    end_effects: list[StateMutation] = Field(min_length=1)

    @model_validator(mode="after")
    def anchors_are_distinct(self) -> "ChapterAnchors":
        begin = (self.begin_subject.id, self.begin_verb.casefold(), self.begin_object.id)
        end = (self.end_subject.id, self.end_verb.casefold(), self.end_object.id)
        if begin == end:
            raise ValueError("chapter begin and end anchors must be distinct")
        return self


class ChapterAnchorsArtifact(BaseModel):
    anchors: list[ChapterAnchors] = Field(min_length=1)


class PlotNodeProposal(BaseModel):
    location_id: str
    subject: EntityRef
    verb: str = Field(min_length=1)
    object: EntityRef
    purpose: str = Field(min_length=1)
    narrative_function: str | None = None
    taxonomy_id: str | None = None
    taxonomy_movement_id: str | None = None
    depends_on_node_ids: list[str] = Field(default_factory=list)
    preconditions: list[StatePredicate] = Field(default_factory=list)
    effects: list[StateMutation] = Field(min_length=1)
    intention: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    consequence: str = Field(min_length=1)


class PlotNode(BaseModel):
    id: str
    chapter_id: str
    node_type: NodeType
    location_id: str
    subject: EntityRef
    verb: str = Field(min_length=1)
    object: EntityRef
    timestamp: int = Field(ge=0)
    global_order: int = Field(ge=1)
    local_order: int = Field(ge=1)
    target_words: int = Field(ge=1)
    goals: list[NodeGoal] = Field(min_length=1)
    depends_on_node_ids: list[str] = Field(default_factory=list)
    preconditions: list[StatePredicate] = Field(default_factory=list)
    effects: list[StateMutation] = Field(default_factory=list)
    intention: str = ""
    conflict: str = ""
    consequence: str = ""

    @property
    def event(self) -> str:
        return f"{self.subject.name} {self.verb} {self.object.name}"


class PlotNodeReview(BaseModel):
    accepted: bool
    causal: bool
    intentional: bool
    conflict_present: bool
    continuous: bool
    novel: bool
    advances_ending: bool
    world_consistent: bool
    emotionally_effective: bool = True
    aligns_with_cen: bool = False
    review_focus: list[ReviewFocus] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    revised: PlotNodeProposal | None = None

    @model_validator(mode="after")
    def acceptance_is_earned(self) -> "PlotNodeReview":
        checks = (
            "causal", "intentional", "conflict_present", "continuous", "novel",
            "advances_ending", "world_consistent", "emotionally_effective",
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
    kind: EntityKind = "concept"
    state: dict[str, str] = Field(default_factory=dict)
    knowledge: list[str] = Field(default_factory=list)
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


class StoryStateSnapshot(BaseModel):
    entities: list[NarrativeEntity] = Field(default_factory=list)
    relations: list[EntityRelation] = Field(default_factory=list)
