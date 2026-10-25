"""What the playwright hands the stage: scenes, beats and their revisions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...schemas import ModelId


class SceneCastBrief(BaseModel):
    """One character on stage in a scene, with the objective the script gives them there."""

    character_id: ModelId
    name: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    public_face: str = ""


class BeatBrief(BaseModel):
    """One plan event the scene must reach, as the director sees it.

    The actors never receive this: they are told a situation, an objective and a note. The beat
    is the director's own yardstick for whether the scene may move on.
    """

    event_id: ModelId
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    promise_brief: str = ""
    required_gates: list[str] = Field(default_factory=list)
    dependencies: list[str] | None = None
    supporting_fact_ids: list[str] = Field(default_factory=list)


class SceneBrief(BaseModel):
    """Everything one scene of the performance is built from, persisted for the audit."""

    scene_id: ModelId
    number: int = Field(ge=1)
    chapter_id: ModelId
    act_number: int = Field(ge=1)
    location_id: str | None = None
    location_name: str = ""
    setting: str = Field(min_length=1)
    cast: list[SceneCastBrief] = Field(min_length=1)
    beats: list[BeatBrief] = Field(min_length=1)
    gate_facts: list[str] = Field(default_factory=list)
    scripted_lines: list[str] = Field(default_factory=list)
    closes_play: bool = False


class RevisedBeat(BaseModel):
    """A changed outcome for an existing, still unperformed event."""

    model_config = ConfigDict(extra="forbid")
    event_id: ModelId
    outcome: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    dependencies: list[str] | None = None
    supporting_fact_ids: list[str] = Field(default_factory=list)


class RevisedScene(BaseModel):
    """One remaining scene, kept or omitted without changing its cast or event identities."""

    model_config = ConfigDict(extra="forbid")
    scene_id: ModelId
    keep: bool
    setting: str = ""
    beats: list[RevisedBeat] = Field(default_factory=list)
    objectives: dict[str, str] = Field(
        default_factory=dict,
        description="Changed objectives keyed by original cast ID; omitted actors keep theirs.",
    )


class FutureConflict(BaseModel):
    """A cited conflict between performed turns and an unperformed event."""

    model_config = ConfigDict(extra="forbid")
    invalidated_event_ids: list[str] = Field(default_factory=list)
    evidence_turn_ids: list[str] = Field(default_factory=list)
    reason: str = ""


class FutureRevision(BaseModel):
    """A bounded revision of scenes that have not yet been performed."""

    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1)
    scenes: list[RevisedScene] = Field(default_factory=list)
