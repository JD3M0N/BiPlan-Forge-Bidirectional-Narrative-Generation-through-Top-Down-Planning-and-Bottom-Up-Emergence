"""What a story was asked for, and the world the architect derived from it."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from ..planning.catalog_types import ModelId
from ..planning.profiles import NarrativeProfile


class StoryRequest(BaseModel):
    """Represent StoryRequest data and behavior."""

    model_config = ConfigDict(extra="forbid")

    original_prompt: str
    processed_prompt: str = Field(
        default="",
        description=(
            "Faithful English paraphrase of explicit facts only; preserve "
            "uncertainty and restriction scope. No invented relationships, "
            "causes or endings."
        ),
    )
    title: str = Field(min_length=1)
    language: str = "Spanish"
    genre: str
    tone: str
    narrative_profile: NarrativeProfile
    premise: str = Field(
        description=(
            "Core conflict grounded only in explicit user facts, without resolving uncertainties."
        )
    )
    constraints: list[str] = Field(default_factory=list)
    creative_directions: list[str] = Field(
        default_factory=list,
        description=(
            "Optional inferred creative proposals, never user requirements or established facts."
        ),
    )
    # 7.12. The only field kept in the author's language: "lenguaje jovial con cubanismos"
    # reached the writers as the English label "Jovial", and the register was lost.
    style_request: str = Field(
        default="",
        description=(
            "The user's own instructions about how the story is written (register, voice, "
            "slang, vocabulary, audience, brevity), copied verbatim and untranslated. Empty "
            "when the request says nothing about how to write. Never plot facts."
        ),
    )

    def agent_spec(self) -> dict:
        """Return trusted downstream data without replaying the raw prompt.

        style_request is left out: only the agents that write the prose receive it, each as an
        instruction of its own rather than one more JSON field.
        """
        return self.model_dump(mode="json", exclude={"original_prompt", "style_request"})


class SkeletonMatch(BaseModel):
    """Auditable relevance score for one plot skeleton against a story request."""

    skeleton_id: ModelId
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

    id: ModelId
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class StoryObject(BaseModel):
    """Represent StoryObject data and behavior."""

    id: ModelId
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
        """Reject duplicate location or object ids."""
        location_ids = [item.id for item in self.locations]
        object_ids = [item.id for item in self.objects]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("world location ids must be unique")
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("world object ids must be unique")
        return self
