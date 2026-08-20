"""Shared factual contracts for the Top-Down 4.0 pipeline.

This module deliberately contains no Promise-Progress-Payoff or STORYLINE
implementation details.  It is the stable language used by planning, world,
character, and writing-boundary components.
"""

from __future__ import annotations

from typing import Literal

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
    requested_chapters: int | None = Field(default=None, ge=1, le=80)
    premise: str
    constraints: list[str] = Field(default_factory=list)

    def agent_spec(self) -> "AgentStorySpec":
        """Return trusted downstream data without replaying the raw user prompt."""
        return AgentStorySpec.model_validate(
            self.model_dump(exclude={"original_prompt"})
        )


class AgentStorySpec(BaseModel):
    processed_prompt: str
    title: str
    language: str
    genre: str
    tone: str
    target_words: int
    requested_chapters: int | None = None
    premise: str
    constraints: list[str] = Field(default_factory=list)


class TaxonomyOptionReference(BaseModel):
    taxonomy_id: str = Field(min_length=1)
    option_id: str = Field(min_length=1)


class TaxonomyApplication(BaseModel):
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
            raise ValueError("taxonomy options may only come from selected taxonomies")
        return self


class TaxonomyBrief(BaseModel):
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
        "Use this material as a flexible palette. Preserve selected reader "
        "expectations but merge, omit, reorder, or reinterpret non-core conventions."
    )


MICEThread = Literal["milieu", "inquiry", "character", "event"]


class StoryFrame(BaseModel):
    central_question: str = Field(min_length=1)
    a_plot_goal: str = Field(min_length=1)
    b_plot_need: str = Field(min_length=1)
    outer_mice_thread: MICEThread
    opening_state: str = Field(min_length=1)
    closing_state: str = Field(min_length=1)
    internal_change_enables_external_resolution: str = Field(min_length=1)


class StoryPlanArtifact(BaseModel):
    logline: str
    theme: str
    central_conflict: str
    progression: list[str] = Field(min_length=3)
    intended_ending: str
    story_frame: StoryFrame
    taxonomy_application: TaxonomyApplication


class Location(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    connected_location_ids: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class StoryObject(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    initial_location_id: str | None = None
    initial_owner_character_id: str | None = None
    portable: bool = True


class WorldArtifact(BaseModel):
    setting: str
    time_period: str
    rules: list[str] = Field(min_length=1)
    locations: list[Location] = Field(min_length=1)
    objects: list[StoryObject] = Field(default_factory=list)
    atmosphere: str

    @model_validator(mode="after")
    def references_are_consistent(self) -> "WorldArtifact":
        location_ids = [item.id for item in self.locations]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("world location ids must be unique")
        known = set(location_ids)
        for location in self.locations:
            unknown = set(location.connected_location_ids) - known
            if unknown:
                raise ValueError(f"location {location.id} has unknown connections: {sorted(unknown)}")
        object_ids = [item.id for item in self.objects]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("world object ids must be unique")
        unknown_locations = {
            item.initial_location_id for item in self.objects
            if item.initial_location_id and item.initial_location_id not in known
        }
        if unknown_locations:
            raise ValueError(f"objects reference unknown locations: {sorted(unknown_locations)}")
        return self


SliderName = Literal["sympathy", "competence", "proactivity"]
ArcType = Literal["positive", "negative", "flat"]


class SliderRange(BaseModel):
    start: int = Field(ge=1, le=10)
    target: int = Field(ge=1, le=10)
    rationale: str = Field(min_length=1)


class CharacterSliderArc(BaseModel):
    sympathy: SliderRange
    competence: SliderRange
    proactivity: SliderRange
    focus: SliderName
    arc_type: ArcType
    steadfast_truth: str | None = None
    world_change: str | None = None
    justification: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_arc_shape(self) -> "CharacterSliderArc":
        ranges = {
            "sympathy": self.sympathy,
            "competence": self.competence,
            "proactivity": self.proactivity,
        }
        focused = ranges[self.focus]
        others = [value for name, value in ranges.items() if name != self.focus]
        if self.arc_type == "positive":
            if focused.start > 4 or focused.target < 7:
                raise ValueError("positive focus must grow from low to high")
            if any(value.start < 6 or value.target < 6 for value in others):
                raise ValueError("positive arcs require two stable functional strengths")
        elif self.arc_type == "negative":
            if focused.start - focused.target < 3:
                raise ValueError("negative focus must fall by at least three points")
            if max(value.target for value in ranges.values()) < 6:
                raise ValueError("negative arcs may not end with all sliders low")
        else:
            if any(abs(value.target - value.start) > 1 for value in ranges.values()):
                raise ValueError("flat arcs keep every slider approximately stable")
            if sum(value.start >= 6 for value in ranges.values()) < 2:
                raise ValueError("flat arcs require at least two stable strengths")
            if not (self.steadfast_truth and self.world_change):
                raise ValueError("flat arcs require steadfast_truth and world_change")
        return self


class CharacterProfile(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str
    narrative_role: str
    ensemble_seat: str
    competence_domain: str
    jungian_archetype: str
    want: str
    need: str
    misbelief: str
    wound: str
    strength: str
    flaw: str
    flaw_cost: str
    unspoken_rule: str
    voice: str
    notices: str
    goal: str
    motivation: str
    conflict: str
    arc: str
    importance: Literal["main", "supporting"] = "supporting"
    initial_location_id: str | None = None
    initial_status: str = "alive"
    initial_knowledge: list[str] = Field(default_factory=list)
    slider_arc: CharacterSliderArc | None = None


class CharacterRelationship(BaseModel):
    source_character_id: str
    target_character_id: str
    kind: str = Field(min_length=1)
    state: str = Field(min_length=1)


class CharactersArtifact(BaseModel):
    characters: list[CharacterProfile] = Field(min_length=1)
    relationships: list[CharacterRelationship] = Field(default_factory=list)

    @model_validator(mode="after")
    def cast_is_valid(self) -> "CharactersArtifact":
        ids = [item.id for item in self.characters]
        names = [item.name.casefold().strip() for item in self.characters]
        if len(ids) != len(set(ids)) or len(names) != len(set(names)):
            raise ValueError("character ids and names must be unique")
        mains = [item for item in self.characters if item.importance == "main"]
        if not mains:
            raise ValueError("at least one main character is required")
        missing = [item.name for item in mains if item.slider_arc is None]
        if missing:
            raise ValueError(f"main characters require slider arcs: {', '.join(missing)}")
        known = set(ids)
        for relationship in self.relationships:
            if {relationship.source_character_id, relationship.target_character_id} - known:
                raise ValueError("character relationships must use canonical character IDs")
        return self

    def storyline_cast(self) -> "StorylineCast":
        """Project profiles to factual data; sliders and arc psychology cannot cross."""
        return StorylineCast(
            characters=[StorylineCharacter.model_validate(item.model_dump())
                        for item in self.characters],
            relationships=self.relationships,
        )


class StorylineCharacter(BaseModel):
    id: str
    name: str
    narrative_role: str
    goal: str
    motivation: str
    conflict: str
    initial_location_id: str
    initial_status: str = "alive"
    initial_knowledge: list[str] = Field(default_factory=list)


class StorylineCast(BaseModel):
    characters: list[StorylineCharacter] = Field(min_length=1)
    relationships: list[CharacterRelationship] = Field(default_factory=list)


FreytagPhase = Literal["exposition", "rising_action", "climax", "falling_action", "denouement"]


class ChapterPlan(BaseModel):
    id: str
    order: int = Field(ge=1)
    title: str
    abstract: str
    target_words: int = Field(ge=200)
    freytag_phases: list[FreytagPhase] = Field(min_length=1)


class StoryOutlineArtifact(BaseModel):
    premise: str
    synopsis: str
    chapters: list[ChapterPlan] = Field(min_length=1)


class CharacterWritingCard(BaseModel):
    name: str
    want: str
    immediate_behavior: str
    voice: str
    notices: str
    unspoken_rule: str
    flaw_pressure: str
