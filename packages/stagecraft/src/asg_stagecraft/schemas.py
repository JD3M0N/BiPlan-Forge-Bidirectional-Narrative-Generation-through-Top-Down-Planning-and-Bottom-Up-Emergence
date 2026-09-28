"""Data contracts for the Stagecraft artifact pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from .formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from .planning.profiles import NarrativeProfile
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


class SkeletonMatch(BaseModel):
    """Auditable relevance score for one plot skeleton against a story request."""

    skeleton_id: str = Field(pattern=ID_PATTERN)
    score: float = Field(ge=0, le=1)
    lexical_score: float = Field(ge=0, le=1)
    semantic_score: float | None = Field(default=None, ge=0, le=1)
    matched_terms: list[str] = Field(default_factory=list)
    catalog_order: int = Field(ge=0)


class SemanticSkeletonScore(BaseModel):
    """One model-assigned relevance value for a single plot skeleton."""

    skeleton_id: str
    relevance: float = Field(ge=0, le=1)


class SemanticSkeletonRanking(BaseModel):
    """Model-side half of the hybrid skeleton ranking."""

    scores: list[SemanticSkeletonScore] = Field(default_factory=list)


class RoleSuggestion(BaseModel):
    """One optional pairing of narrative function and surface persona for a character."""

    functional_role: str = Field(min_length=1)
    persona: str = ""
    sketch: str = Field(min_length=1)


class NarrativeBlueprintDraft(BaseModel):
    """Structural reading of a premise, proposed before the world and cast exist."""

    macroplot_id: str = Field(min_length=1)
    macroplot_reading: str = Field(min_length=1)
    subplot_ids: list[str] = Field(default_factory=list, max_length=3)
    role_suggestions: list[RoleSuggestion] = Field(default_factory=list)
    unexpected_angle: str = Field(min_length=1)


class NarrativeBlueprint(NarrativeBlueprintDraft):
    """One blueprint plus the ranking evidence that produced it."""

    considered: list[SkeletonMatch] = Field(default_factory=list)
    semantic_used: bool = False


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
    functional_role: str = ""
    persona: str = ""

    @field_validator("functional_role", "persona", mode="before")
    @classmethod
    def normalize_optional_label(cls, value: object, info: ValidationInfo) -> str:
        """Normalize optional role vocabulary and blank values outside the catalog."""
        if not isinstance(value, str):
            return ""
        normalized = value.strip().casefold().replace(" ", "_").replace("-", "_")
        if info.field_name == "functional_role" and normalized:
            from .planning.skeletons import FunctionalRole

            if normalized not in {role.value for role in FunctionalRole}:
                return ""
        return normalized


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
    """One chapter as the planner proposed it, before graph.py has judged the plan."""

    id: str = Field(pattern=ID_PATTERN)
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    dramatic_goal: str = Field(min_length=1)
    opening_state: str = Field(min_length=1)
    turning_point: str = Field(min_length=1)
    closing_state: str = Field(min_length=1)


class ChapterPlan(ChapterDraft):
    """One chapter of a plan materialize_plan already validated.

    The fields match ChapterDraft deliberately: what separates the two is provenance,
    not shape. Only graph.py mints a ChapterPlan, and it does so after the invariants
    hold, so a signature asking for one cannot be handed raw model output. This mirrors
    the StoryPlanDraft/StoryPlan split at the level of a single chapter; collapsing it
    would let unvalidated chapters reach the drafter and the audit.
    """


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


PromiseKind = Literal["story_direction", "character_conflict", "genre_structure", "tone"]


class PromiseBeat(BaseModel):
    """One ledger beat anchored to an event the validated plan already contains.

    The anchor is the whole point of the contract: a beat cites a PlotEvent ID instead of
    describing a moment of its own, so the ledger can annotate the frozen storyline without
    ever being able to ask for a new one.
    """

    event_id: str = Field(
        pattern=ID_PATTERN,
        description="ID of a PlotEvent the validated plan already contains.",
    )


class PromiseOpening(PromiseBeat):
    """The event where one promise becomes visible to the reader."""

    signal: str = Field(min_length=1)
    reader_expectation: str = Field(min_length=1)


class PromiseProgress(PromiseBeat):
    """One signposted advance that keeps a promise alive between opening and payoff."""

    id: str = Field(pattern=ID_PATTERN)
    observable_delta: str = Field(min_length=1)
    new_cost_or_information: str = Field(min_length=1)


class PromisePayoff(PromiseBeat):
    """The event that answers one promise, and the preparation that earned the answer."""

    answer: str = Field(min_length=1)
    cost: str = Field(min_length=1)
    prepared_by_progress_ids: list[str] = Field(min_length=1)
    surprising_without_breach: str = Field(min_length=1)


class PromiseContract(BaseModel):
    """One expectation the story opens, signposts, and pays off."""

    id: str = Field(pattern=ID_PATTERN)
    kind: PromiseKind
    subject: str = Field(min_length=1)
    dramatic_question: str = Field(min_length=1)
    opening: PromiseOpening
    progress: list[PromiseProgress] = Field(min_length=1)
    payoff: PromisePayoff


class PromiseLedgerDraft(BaseModel):
    """A promise ledger as the model proposed it, before promises.py has judged it."""

    primary_promise_id: str = Field(pattern=ID_PATTERN)
    promises: list[PromiseContract] = Field(min_length=2, max_length=8)


class PromiseLedger(PromiseLedgerDraft):
    """A ledger materialize_ledger already checked against the frozen plan.

    The fields it adds are all derived, never authored: chapter_by_event resolves each anchor
    through the plan, observations record non-blocking findings, and the prompt blocks keep the
    exact text that travelled to the model so a run stays auditable.
    """

    chapter_by_event: dict[str, str] = Field(default_factory=dict)
    observations: list[str] = Field(default_factory=list)
    chapter_blocks: dict[str, str] = Field(default_factory=dict)
    critic_block: str = ""


class PromiseCheck(BaseModel):
    """One critic verdict on whether the draft honored a promise of the ledger."""

    promise_id: str = Field(pattern=ID_PATTERN)
    opened: bool
    progressed: bool
    paid: bool
    verdict: Literal["fulfilled", "weak", "broken"]
    evidence: str = Field(min_length=1)


class PromiseAuditEntry(BaseModel):
    """One promise of the ledger next to the verdict the critic returned for it."""

    promise_id: str = Field(pattern=ID_PATTERN)
    kind: PromiseKind
    primary: bool
    verdict: Literal["fulfilled", "weak", "broken"]
    opened: bool
    progressed: bool
    paid: bool
    evidence: str = ""


class PromiseAuditArtifact(BaseModel):
    """Observed promise fulfillment for one run, never a target handed to any agent."""

    promises: int = Field(default=0, ge=0)
    fulfilled: int = Field(default=0, ge=0)
    weak: int = Field(default=0, ge=0)
    broken: int = Field(default=0, ge=0)
    fulfilled_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    entries: list[PromiseAuditEntry] = Field(default_factory=list)


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


class ScriptLine(BaseModel):
    """One line of a scene: words a character speaks, or a stage direction the audience sees."""

    kind: Literal["dialogue", "direction"]
    speaker_id: str = Field(
        default="",
        description="Character ID of the speaker, for a dialogue line. Empty for a direction.",
    )
    parenthetical: str = Field(
        default="",
        description=(
            "Optional brief acting note for a dialogue line, without parentheses. "
            "Empty for a direction."
        ),
    )
    actor_ids: list[str] = Field(
        default_factory=list,
        description="Character IDs of everyone who acts in a stage direction. Empty for dialogue.",
    )
    text: str = Field(
        min_length=1,
        description=(
            "The spoken words for dialogue, or what the audience sees or hears, for a direction. "
            "In the fiction language."
        ),
    )


class SceneCastMember(BaseModel):
    """One character on stage in a scene, with the objective the actor plays there."""

    character_id: str = Field(description="Character ID from the ACT ANCHOR INDEX.")
    objective: str = Field(
        min_length=1,
        description=(
            "In English: what this character wants in this scene, as a concrete, playable want. "
            "Never printed in the rendered script."
        ),
    )


class ScriptSceneDraft(BaseModel):
    """One scene as the model proposed it, before script.py has judged it."""

    event_ids: list[str] = Field(
        min_length=1,
        description="Plan event IDs this scene stages, from the ACT ANCHOR INDEX, in plan order.",
    )
    location_id: str | None = Field(
        default=None,
        description=(
            "Location ID from the ACT ANCHOR INDEX. Null only when none of this scene's events "
            "declares a location."
        ),
    )
    setting: str = Field(
        min_length=1,
        description="Opening stage direction in the fiction language: place and moment, as seen.",
    )
    cast: list[SceneCastMember] = Field(
        min_length=1,
        description="Every character on stage in this scene.",
    )
    lines: list[ScriptLine] = Field(min_length=1)


class ActScriptDraft(BaseModel):
    """One chapter written as an act of scenes, before script.py has judged it."""

    scenes: list[ScriptSceneDraft] = Field(min_length=1)


class ScriptScene(ScriptSceneDraft):
    """One scene script.py already validated against the frozen plan.

    id and number are derived, never authored: the model proposes a ScriptSceneDraft and
    materialize_act mints the identity once the anchors and staging hold.
    """

    id: str = Field(pattern=ID_PATTERN)
    number: int = Field(ge=1)


class ActScript(BaseModel):
    """One act script.py already validated: a chapter staged as scenes."""

    chapter_id: str = Field(pattern=ID_PATTERN)
    number: int = Field(ge=1)
    title: str = Field(min_length=1)
    scenes: list[ScriptScene] = Field(min_length=1)
    observations: list[str] = Field(default_factory=list)

    def as_draft(self) -> ActScriptDraft:
        """Strip validated identity, returning the shape the Script Writer receives and returns."""
        return ActScriptDraft(
            scenes=[
                ScriptSceneDraft(**scene.model_dump(exclude={"id", "number"}))
                for scene in self.scenes
            ]
        )


class CastNote(BaseModel):
    """One optional description of a character for the printed cast list."""

    character_id: str = Field(description="Character ID from characters.json.")
    description: str = Field(min_length=1)


class ScriptFrame(BaseModel):
    """Labels and cast notes for the printed script, created once per run."""

    cast_heading: str = Field(min_length=1, description="Localized heading, e.g. 'Personajes'.")
    act_label: str = Field(min_length=1, description="Localized act word, e.g. 'Acto'.")
    scene_label: str = Field(min_length=1, description="Localized scene word, e.g. 'Escena'.")
    cast: list[CastNote] = Field(default_factory=list)


class ScriptPresentation(StoryPresentation):
    """Localized titles plus the printed-script frame, created when script writing begins."""

    frame: ScriptFrame


class PlayCastMember(BaseModel):
    """One member of the dramatis personae, as printed in script.json."""

    character_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    description: str = ""


class PlayScript(BaseModel):
    """The complete theater script contract: script.json.

    This is a documented JSON contract, not a shared Python type: a reader outside this package
    need not import asg_stagecraft, so every field here is meant to be read from the file itself.
    """

    contract_version: str = "1"
    title: str = Field(min_length=1)
    language: str
    script_method: ScriptMethod
    cast_heading: str = Field(min_length=1)
    act_label: str = Field(min_length=1)
    scene_label: str = Field(min_length=1)
    cast: list[PlayCastMember] = Field(default_factory=list)
    acts: list[ActScript] = Field(min_length=1)


class ActMetrics(BaseModel):
    """Record observed act size and staging without defining a target."""

    chapter_id: str = Field(pattern=ID_PATTERN)
    scenes: int = Field(ge=0)
    events: int = Field(ge=0)
    lines: int = Field(default=0, ge=0)
    dialogue_lines: int = Field(default=0, ge=0)
    direction_lines: int = Field(default=0, ge=0)
    words: int = Field(default=0, ge=0)


class CharacterStageMetrics(BaseModel):
    """Record how much stage time one character received, across the whole script."""

    character_id: str = Field(pattern=ID_PATTERN)
    scenes: int = Field(default=0, ge=0)
    lines: int = Field(default=0, ge=0)
    words: int = Field(default=0, ge=0)
    actions: int = Field(default=0, ge=0)


class ScriptMetrics(BaseModel):
    """Record observed theater-script characteristics without budget compliance."""

    narrative_profile: NarrativeProfile
    script_method: ScriptMethod
    words: int = Field(ge=0)
    acts: int = Field(ge=0)
    scenes: int = Field(ge=0)
    events: int = Field(ge=0)
    lines: int = Field(default=0, ge=0)
    dialogue_lines: int = Field(default=0, ge=0)
    direction_lines: int = Field(default=0, ge=0)
    dialogue_words: int = Field(default=0, ge=0)
    direction_words: int = Field(default=0, ge=0)
    setting_words: int = Field(default=0, ge=0)
    dialogue_word_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    words_per_dialogue_line: float = Field(default=0.0, ge=0.0)
    words_per_direction: float = Field(default=0.0, ge=0.0)
    idle_cast: int = Field(default=0, ge=0)
    absent_participants: int = Field(default=0, ge=0)
    act_metrics: list[ActMetrics] = Field(default_factory=list)
    character_metrics: list[CharacterStageMetrics] = Field(default_factory=list)


class StoryReview(BaseModel):
    """Represent StoryReview data and behavior."""

    strengths: list[str] = Field(default_factory=list)
    notes: list[RevisionNote] = Field(default_factory=list)
    constraint_checks: list[ConstraintCheck] = Field(default_factory=list)
    promise_checks: list[PromiseCheck] = Field(default_factory=list)


class ChapterCraftEvidence(BaseModel):
    """Craft deficits observed in one drafted chapter, worded for the critic."""

    chapter_id: str = Field(pattern=ID_PATTERN)
    observations: list[str] = Field(default_factory=list)


class CraftEvidenceArtifact(BaseModel):
    """Deterministic craft evidence and the exact block handed to the Drama Critic."""

    chapters: list[ChapterCraftEvidence] = Field(default_factory=list)
    prompt_block: str = ""


class ChapterMetrics(BaseModel):
    """Record observed chapter size and prose craft without defining a target."""

    chapter_id: str = Field(pattern=ID_PATTERN)
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


class WriterCandidateDiagnostic(BaseModel):
    """Explain why one Writer candidate was rejected and how to correct it."""

    code: Literal[
        "EMPTY_CHAPTER_BODY",
        "MARKDOWN_HEADINGS",
        "UNCHANGED_SIGNIFICANT_NOTES",
        "INVALID_SCRIPT_ACT",
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
    warning_code: Literal["WRITER_REVISION_REJECTED", "SCRIPT_REVISION_REJECTED"] | None = None


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
    """One attempt at one model call, and where in the pipeline it was made.

    Since 7.2 every attempt of a logical call shares its call_id, duration_seconds is that
    attempt's own latency and wait_seconds the waiting that preceded it, so nothing adds up
    earlier attempts; stage is the pipeline stage and agent the one that asked. Before 7.2 each
    attempt had its own call_id, durations accumulated retries and stage repeated operation.
    """

    call_id: str
    operation: str
    stage: str
    agent: str = ""
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
    """A run's model usage: logical calls, the attempts they took, and auxiliary requests.

    calls and failed_calls count logical calls (one call_id each; failed when its last attempt
    failed), attempts and failed_attempts count requests, and auxiliary_calls the count_tokens
    preflights, which are never calls. Before 7.2 calls mixed all three.
    """

    records: list[LLMUsageRecord] = Field(default_factory=list)
    calls: int = 0
    failed_calls: int = 0
    attempts: int = 0
    failed_attempts: int = 0
    auxiliary_calls: int = 0
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
    story_format: StoryFormat = StoryFormat.NARRATIVE
    script_method: ScriptMethod | None = None
    # Both stay None outside a simulated run, so a narrative or script run's metadata is
    # byte-identical to the one the same pipeline wrote before the hybrid stages existed.
    narrative_voice: NarrativeVoice | None = None
    actor_memory: ActorMemory | None = None
    # The profile the run was generated with, so a run that failed before request.json existed
    # still says what it was asked for (7.2).
    narrative_profile: NarrativeProfile | None = None
    # The model the performance ran on, set only for a simulated run whose performance had a model,
    # key or pace of its own (GEMINI_STAGE_*, 7.4). None means the performance ran on `model`, as
    # every run before 7.4 did; llm_calls.jsonl names the model of each call.
    stage_model: str | None = None
