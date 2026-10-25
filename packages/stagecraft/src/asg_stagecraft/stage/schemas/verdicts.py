"""How the director judges a beat: evidence, facts, outcomes and the log it leaves."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...schemas import ModelId
from .props import ItemActionDraft


class EvidenceSource(BaseModel):
    """An exact, channel-specific citation; witnesses are derived by the engine."""

    model_config = ConfigDict(extra="forbid")
    turn_id: str
    channel: Literal["action", "speech", "thought"]
    excerpt: str = Field(min_length=1)


class WorldItemDraft(ItemActionDraft):
    """An object affected by the world, with its current holder named explicitly."""

    actor: str = ""


class OutcomePart(BaseModel):
    """One clause of a beat's outcome, and whether the performance has shown it."""

    model_config = ConfigDict(extra="forbid")

    part: str = Field(
        min_length=1,
        description=(
            "In the fiction language: one clause of the outcome. A fixed clause is copied as given."
        ),
    )
    shown: bool = Field(description="True only if an audience would have seen this happen.")
    evidence: list[str] = Field(
        default_factory=list,
        description="Turn IDs from the transcript that show it. Required when shown is true.",
    )

    sources: list[EvidenceSource] = Field(default_factory=list)


class TypedOutcomePart(OutcomePart):
    """A clause tagged with who can make it happen (7.17, the typed_clauses option)."""

    kind: Literal["decision", "revelation", "world"] = Field(
        default="decision",
        description=(
            "decision: someone on stage chooses or does it. revelation: someone on stage tells "
            "or discovers a fact. world: the world or someone off stage does it - a journey, an "
            "arrival, a ship leaving - which the characters cannot act out."
        ),
    )


class BeatEvidence(BaseModel):
    """A cited, publicly visible fragment and its provenance."""

    clause_id: str
    turn_id: str
    kind: Literal["action", "declaration", "world_event"]
    excerpt: str
    channel: Literal["action", "speech", "thought"] | None = None
    witnesses: list[str] = Field(default_factory=list)
    assessment: Literal["director"] = "director"


class FactProposal(BaseModel):
    """A world change the director says an observable turn established."""

    model_config = ConfigDict(extra="forbid")
    statement: str = Field(min_length=1)
    source_turn_id: str
    supersedes_id: str = ""
    source: EvidenceSource | None = None
    status: Literal["established", "claim", "belief"] = "established"


class StageFact(BaseModel):
    """A director-assessed fact with its observed source and witnesses."""

    id: str
    statement: str
    source_turn_id: str
    kind: Literal["action", "world_event", "declaration", "thought"]
    channel: Literal["action", "speech", "thought"] | None = None
    excerpt: str = ""
    status: Literal["established", "claim", "belief"] = "established"
    witnesses: list[str] = Field(default_factory=list)
    supersedes_id: str = ""
    assessment: Literal["director"] = "director"


class BeatCheckDraft(BaseModel):
    """The director's reading of a beat, as proposed. Whether it landed is derived, not declared.

    The director breaks the outcome into its clauses and says which the performance has shown;
    the engine decides the beat is reached only when every clause is shown with a turn to prove
    it. The first real run showed why: a model asked for one yes-or-no was literal in one scene
    and lenient in another, and one lenient yes closed a mystery without its motive.
    """

    model_config = ConfigDict(extra="forbid")

    facts: list[FactProposal] = Field(default_factory=list)
    parts: list[OutcomePart] = Field(
        min_length=1,
        description="Every clause of the outcome, each judged separately.",
    )
    next_actor_id: str = Field(
        default="",
        description="Character ID who should move next, or empty to let the scene decide.",
    )
    turning_actor_id: str = Field(
        default="",
        description=(
            "Character ID of the one whose change the missing clause needs: who has to give "
            "ground, confess, discover or decide for it to happen. Required when told to name one."
        ),
    )
    notes: list[str] = Field(
        default_factory=list,
        max_length=2,
        description=(
            "In the fiction language: at most two playable notes, as in BeatDirection. When a "
            "turning actor is named, one note is theirs and gives them a reason to change now."
        ),
    )
    stage_event: str = Field(
        default="",
        description=(
            "In the fiction language: something the world itself does that everyone present sees "
            "or hears. Empty unless you are asked for one."
        ),
    )

    world_items: list[WorldItemDraft] = Field(default_factory=list)
    world_basis: list[EvidenceSource] = Field(default_factory=list)
    world_effect: Literal["opportunity", "pressure"] = "pressure"


class TypedBeatCheckDraft(BeatCheckDraft):
    """The director's reading with each clause tagged by kind (7.17, typed_clauses).

    A model of its own, like ActorTurnWithItemsDraft: the schema crosses to the provider, so a
    kind field on every reading would change every director request of the control arm.
    """

    parts: list[TypedOutcomePart] = Field(
        min_length=1,
        description="Every clause of the outcome, each judged separately and tagged by kind.",
    )


class DirectorEntry(BaseModel):
    """One call to the director, with what the engine made of it: a line of director.jsonl."""

    decision_id: str = ""
    scene_id: ModelId
    beat_event_id: str
    beat_index: int = Field(ge=0)
    mode: Literal["open", "check", "turn", "stall", "final"]
    after_turn: int = Field(ge=0)
    draft: dict | None = None
    achieved: bool | None = None
    evidence: list[str] = Field(default_factory=list)
    proofs: list[BeatEvidence] = Field(default_factory=list)
    accepted_facts: list[StageFact] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    turning_actor_id: str = ""
    turning_fallback: bool = False
    stage_event: str = ""
    failed: bool = False
    progress: dict[str, list[str]] = Field(default_factory=dict)
    stagnant_checks: int = 0


class BeatRecord(BaseModel):
    """What happened to one beat: the direction, every check, and how it closed."""

    event_id: ModelId
    index: int = Field(ge=0)
    opening_actor_id: str = ""
    notes: list[str] = Field(default_factory=list)
    checks: int = Field(default=0, ge=0)
    turns: int = Field(default=0, ge=0)
    achieved: bool = False
    # Reached only after the world stepped in: honest about how, without calling it forced.
    intervened: bool = False
    forced: bool = False
    evidence: list[str] = Field(default_factory=list)
    proofs: list[BeatEvidence] = Field(default_factory=list)
    stage_events: list[str] = Field(default_factory=list)
    turning_actor_id: str = ""
    reaction_turns: int = Field(default=0, ge=0)
    missing: list[str] = Field(default_factory=list)
