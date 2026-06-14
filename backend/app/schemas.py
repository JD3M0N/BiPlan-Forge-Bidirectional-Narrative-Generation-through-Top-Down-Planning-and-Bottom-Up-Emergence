from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, conlist


StoryLength = Literal["short", "medium", "long"]
StoryStatus = Literal["pending", "running", "completed", "failed"]
PipelineMode = Literal["efficient", "full"]
RunStatus = StoryStatus


class CharacterInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=300)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    id: str
    email: EmailStr

    class Config:
        orm_mode = True


class AuthResponse(BaseModel):
    user: UserRead


class StoryGenerateRequest(BaseModel):
    characters: conlist(CharacterInput, min_items=1, max_items=6)
    style: str = Field(min_length=2, max_length=80)
    plot: str = Field(min_length=12, max_length=1500)
    length: StoryLength
    language: str = Field(default="es", min_length=2, max_length=16)
    pipeline_mode: PipelineMode = "efficient"

    def to_input_brief(self) -> dict[str, Any]:
        return {
            "characters": [character.dict() for character in self.characters],
            "style": self.style,
            "plot": self.plot,
            "length": self.length,
            "language": self.language,
            "pipeline_mode": self.pipeline_mode,
        }


class StoryJobCreated(BaseModel):
    id: str
    status: StoryStatus


class StoryBeat(BaseModel):
    title: str
    purpose: str
    stakes: str


class SVOTriplet(BaseModel):
    subject: str
    verb: str
    object: str


class SeedEvent(BaseModel):
    id: str
    summary: str
    purpose: str
    characters: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class CharacterProfile(BaseModel):
    name: str
    role: str
    description: str
    desire: str
    fear: str


class LocationProfile(BaseModel):
    name: str
    description: str
    mood: str


class ObjectProfile(BaseModel):
    name: str
    significance: str


class EntityRelation(BaseModel):
    source: str
    relation: str
    target: str


class ArchitectOutline(BaseModel):
    premise: str
    synopsis: str
    beats: list[StoryBeat]
    seed_events: list[SeedEvent]
    climax: str
    resolution: str


class WorldBible(BaseModel):
    characters: list[CharacterProfile]
    locations: list[LocationProfile]
    objects: list[ObjectProfile]
    rules: list[str]
    initial_state: str
    entity_relations: list[EntityRelation] = Field(default_factory=list)


class DirectorAct(BaseModel):
    abstract_act: str
    purpose: str
    target_event_ids: list[str] = Field(default_factory=list)
    environmental_intervention: str
    expected_pressure: str


class DirectorPlan(BaseModel):
    acts: list[DirectorAct]
    constraints: list[str]


class CharacterAction(BaseModel):
    character: str
    event_id: str
    intention: str
    action: str
    memory_used: str
    reflection: str
    world_delta: str


class SimulationLog(BaseModel):
    actions: list[CharacterAction]
    memory_updates: list[str]


class EventNode(BaseModel):
    id: str
    summary: str
    svo: SVOTriplet
    characters: list[str]
    location: str
    time: str
    dependencies: list[str] = Field(default_factory=list)
    dramatic_role: str


class ChapterPlanItem(BaseModel):
    index: int
    title: str
    abstract: str
    event_ids: list[str]
    target_words: int = Field(ge=1)


class ChapterPlan(BaseModel):
    chapters: list[ChapterPlanItem]
    narrative_order: list[str]


class PlotWeave(BaseModel):
    event_graph: list[EventNode]
    entity_graph: list[EntityRelation]
    chapter_plan: ChapterPlan


class DramaRevision(BaseModel):
    revised_beats: list[StoryBeat]
    tension_notes: list[str]
    character_arc_notes: list[str]
    pacing_notes: list[str] = Field(default_factory=list)
    suspense_devices: list[str] = Field(default_factory=list)


class DependencyReview(BaseModel):
    is_consistent: bool
    issues: list[str]
    fixes_applied: list[str]
    narrator_guidance: list[str]
    dependency_notes: list[str] = Field(default_factory=list)


class PlanningRoomResult(BaseModel):
    architect_outline: ArchitectOutline
    world_bible: WorldBible
    director_plan: DirectorPlan
    simulation_log: SimulationLog
    event_graph: list[EventNode]
    entity_graph: list[EntityRelation]
    chapter_plan: ChapterPlan
    drama_revision: DramaRevision
    dependency_review: DependencyReview


class ContextSummary(BaseModel):
    chapter_index: int
    relevant_events: list[str]
    summary: str
    continuity_constraints: list[str]


class ChapterDraft(BaseModel):
    chapter_index: int
    title: str
    text: str
    rewritten: bool = False
    notes: list[str] = Field(default_factory=list)


class ChapterDraftBatch(BaseModel):
    chapters: list[ChapterDraft]


class StoryEvaluation(BaseModel):
    relevance: float = Field(ge=0, le=5)
    coherence: float = Field(ge=0, le=5)
    empathy: float = Field(ge=0, le=5)
    surprise: float = Field(ge=0, le=5)
    engagement: float = Field(ge=0, le=5)
    complexity: float = Field(ge=0, le=5)
    orchestration: float = Field(ge=0, le=5)
    overall: float = Field(ge=0, le=5)
    blocking_issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StoryEvaluationSummary(BaseModel):
    coherence: float
    orchestration: float
    overall: float
    blocking_issues: list[str] = Field(default_factory=list)


class AgentProgress(BaseModel):
    agent_name: str
    label: str
    status: RunStatus
    started_at: str
    finished_at: str | None
    error_message: str | None


class FinalStory(BaseModel):
    title: str
    summary: str
    story_text: str


class StoryListItem(BaseModel):
    id: str
    title: str | None
    summary: str | None
    style: str
    plot: str
    length: StoryLength
    language: str
    pipeline_mode: PipelineMode
    status: StoryStatus
    current_stage: str | None
    progress_percent: int = Field(ge=0, le=100)
    evaluation: StoryEvaluationSummary | None
    created_at: str
    updated_at: str


class StoryDetail(StoryListItem):
    story_text: str | None
    error_message: str | None
    agent_progress: list[AgentProgress]
    evaluation: StoryEvaluation | None


class StoryPacket(BaseModel):
    input_brief: dict[str, Any]
    architect_outline: ArchitectOutline | None = None
    world_bible: WorldBible | None = None
    director_plan: DirectorPlan | None = None
    simulation_log: SimulationLog | None = None
    event_graph: list[EventNode] = Field(default_factory=list)
    entity_graph: list[EntityRelation] = Field(default_factory=list)
    chapter_plan: ChapterPlan | None = None
    drama_revision: DramaRevision | None = None
    dependency_review: DependencyReview | None = None
    context_summaries: list[ContextSummary] = Field(default_factory=list)
    chapter_drafts: list[ChapterDraft] = Field(default_factory=list)
    quality_review: StoryEvaluation | None = None
    final_story: FinalStory | None = None
