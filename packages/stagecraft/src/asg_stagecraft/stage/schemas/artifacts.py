"""What a finished performance is written to disk as."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...formats import ActorMemory, SimulationMode
from ...schemas import ModelId
from .memory import CharacterState
from .props import Prop
from .turns import StageTurn
from .verdicts import BeatRecord, StageFact


class ScenePerformance(BaseModel):
    """One performed scene: its turns, its beats and what each actor took away."""

    scene_id: ModelId
    number: int = Field(ge=1)
    chapter_id: ModelId
    turns: list[StageTurn] = Field(default_factory=list)
    beats: list[BeatRecord] = Field(default_factory=list)
    rejected: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    coda_turns: int = Field(default=0, ge=0)


class PerformanceSettings(BaseModel):
    """The exact knobs one performance ran with, so a reader can repeat or compare it."""

    actor_memory: ActorMemory
    simulation_mode: SimulationMode = SimulationMode.FIXED
    inventory: bool = False
    turns_per_beat: int = Field(ge=2)
    check_every: int = Field(ge=1)
    reaction_turns: int = Field(default=2, ge=0)
    coda_turns: int = Field(default=2, ge=0)
    retrieved_records: int = Field(ge=1)
    recency_decay: float = Field(ge=0.0)
    repetition_threshold: float = Field(ge=0.0, le=1.0)


class PerformanceArtifact(BaseModel):
    """The complete performance contract: performance.json.

    A documented JSON contract like script.json: every field is meant to be read from the file,
    so an analysis script never has to import this package to study a run.
    """

    # 2: achieved is derived from the director's clauses, gates say how they come out, and
    # every director call is logged. A 7.0 run still reads as contract 1.
    # 4: a turn may carry an item_action, and props record where every object began and ended.
    # 5: a turn records the form faults the engine repaired instead of rejecting (repairs).
    contract_version: str = "6"
    narrative_outcome: Literal["resolved", "open", "interrupted"] | None = None
    interruption_reason: str = ""
    planned_events: int | None = None
    facts: list[StageFact] = Field(default_factory=list)
    language: str
    settings: PerformanceSettings
    scenes: list[ScenePerformance] = Field(default_factory=list)
    states: list[CharacterState] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Both empty without an inventory: where every prop started, and where it ended up.
    props: list[Prop] = Field(default_factory=list)
    inventory: list[Prop] = Field(default_factory=list)


class PromiseStoryCheck(BaseModel):
    """A proposed promise judgement anchored in prose and performed turns."""

    model_config = ConfigDict(extra="forbid")
    promise_id: ModelId
    opened: bool
    progressed: bool
    paid: bool
    quote: str = ""
    turn_ids: list[str] = Field(default_factory=list)


class PromiseStoryAuditDraft(BaseModel):
    """All promise judgements proposed after narrating the performance."""

    checks: list[PromiseStoryCheck] = Field(default_factory=list)
