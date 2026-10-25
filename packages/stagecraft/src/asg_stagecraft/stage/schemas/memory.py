"""What a character carries between turns: state, memory records and reflection."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...schemas import ModelId
from .vocabulary import MemoryKind


class RelationshipState(BaseModel):
    """One character's current standing towards another, replaced rather than accumulated.

    Consolidating instead of appending is deliberate: a log that records "allies" and then
    "enemies" without resolving them leaves an actor holding both at once, and it starts acting
    incoherently. The history stays in the memory records; the state is what the actor reads.
    """

    character_id: ModelId
    stance: str = Field(min_length=1)
    reason: str = ""


class CharacterState(BaseModel):
    """One character's evolving state, written by their own reflection at each scene's end."""

    character_id: ModelId
    scene_number: int = Field(ge=0)
    emotion: str = ""
    goal: str = ""
    commitment: str = ""
    cover_story: str = ""
    change_condition: str = ""
    source_turn_id: str = ""
    relationships: list[RelationshipState] = Field(default_factory=list)
    evidence: str = ""


class MemoryRecord(BaseModel):
    """One entry in a character's own memory stream.

    ``importance`` is the character's own sense of how much a moment mattered, which is what the
    retrieval scoring uses; it is never shown to any agent as a number.
    """

    id: str
    character_id: ModelId
    kind: MemoryKind
    scene_number: int = Field(ge=0)
    turn_id: str = ""
    text: str = Field(min_length=1)
    participants: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryRetrieval(BaseModel):
    """One retrieval, with the score breakdown that produced it, kept for the audit."""

    character_id: ModelId
    scene_number: int = Field(ge=0)
    turn_number: int = Field(ge=1)
    query: str
    record_id: str
    score: float
    recency: float
    importance: float
    relevance: float
    company: float


class ReflectionDraft(BaseModel):
    """What one character takes away from a scene, in their own first person."""

    model_config = ConfigDict(extra="forbid")

    evidence: list[str] = Field(
        default_factory=list,
        description="Exact excerpts of the scene supporting changed commitments or beliefs.",
    )
    summary: str = Field(
        min_length=1,
        description=(
            "In the fiction language, first person: what I did and what happened to "
            "me in this scene."
        ),
    )
    beliefs: list[str] = Field(
        default_factory=list,
        max_length=4,
        description=(
            "In the fiction language, first person: what I now believe that I did not believe "
            "before. Only what this scene could have taught me."
        ),
    )
    relationships: list[RelationshipState] = Field(
        default_factory=list,
        description=(
            "How I stand towards each character I dealt with now, replacing how I stood before."
        ),
    )
    emotion: str = Field(
        default="", description="In the fiction language: one word for my mood after this scene."
    )
    goal: str = Field(
        default="", description="In the fiction language: what I am trying to do next."
    )
    commitment: str = Field(
        default="", description="In the fiction language: what I am still resolved to do."
    )
    cover_story: str = Field(
        default="", description="In the fiction language: what I intend others to believe."
    )
    change_condition: str = Field(
        default="", description="In the fiction language: what I would need to see to reconsider."
    )
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How much this scene mattered to me, from 0 for routine to 1 for life-changing."
        ),
    )
