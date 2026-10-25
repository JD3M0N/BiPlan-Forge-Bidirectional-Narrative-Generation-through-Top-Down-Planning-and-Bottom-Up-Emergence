"""What an actor declares in one turn, and what the stage made of it."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ...schemas import ModelId
from .props import ItemAction, ItemActionDraft
from .vocabulary import Tactic, TurnVisibility

# --------------------------------------------------------------------------------------
# The performance
# --------------------------------------------------------------------------------------


class ActorTurnDraft(BaseModel):
    """One turn as the actor proposed it, before stage/validation.py has judged it."""

    model_config = ConfigDict(extra="forbid")

    thought: str = Field(
        default="",
        description=(
            "In the fiction language, first person: the subtext - what the character notices, "
            "fears or keeps quiet and does NOT say, such as a doubt or a lie they are telling. "
            "Never what they plan to do next. Nobody else ever perceives it. Leave it empty "
            "unless it differs from what they say and do."
        ),
    )
    action: str = Field(
        default="",
        description=(
            "In the fiction language, third person present and without the character's own name, "
            "as a stage direction: one visible gesture in a short clause, 'cruza los brazos', "
            "never 'cruzo los brazos'. Only what an audience would see; no thoughts, no "
            "backstory, no trailing clause about its effect ('haciendo que...'). Empty when they "
            "only speak."
        ),
    )
    speech: str = Field(
        default="",
        description=(
            "In the fiction language: exactly the words the character says, with no quotation "
            "marks and no name prefix. Short, as people talk: one thing, said now. Empty when "
            "they only act."
        ),
    )
    addressed_to: list[str] = Field(
        default_factory=list,
        description=(
            "The names of the characters this turn is directed at, as listed under CONTIGO EN "
            "ESCENA. Empty only when addressed to everyone present."
        ),
    )
    visibility: TurnVisibility = Field(
        default="public",
        description=(
            "'public' when everyone on stage perceives it, 'whisper' when only addressed_to do. "
            "A whisper needs the name of whoever it is for in addressed_to."
        ),
    )
    tactic: Tactic = Field(description="The move this turn tries, from the fixed list.")
    goal_after: str = Field(
        default="", description="My current private goal after this move, if it changed."
    )
    commitment_after: str = Field(
        default="", description="My private commitment after this move, if it changed."
    )
    cover_story_after: str = Field(
        default="", description="The account I privately intend to maintain, if it changed."
    )
    change_condition_after: str = Field(
        default="", description="What I would need to see to reconsider, if it changed."
    )

    state_evidence: str = Field(
        default="",
        description="Exact excerpt of this turn supporting a changed goal or commitment.",
    )


class ActorTurnWithItemsDraft(ActorTurnDraft):
    """One turn from an actor who may handle objects: the inventory's response schema.

    A separate model on purpose. The schema of every structured call crosses to the provider,
    so asking for an object field in a run without an inventory would change every actor
    request in the corpus; this one is only ever requested when the option is on.
    """

    item_action: ItemActionDraft = Field(
        default_factory=ItemActionDraft,
        description=(
            "What you do with an object this turn. Leave verb as 'none' unless handling one is "
            "the move. Your action must say in words what you do with it."
        ),
    )

    item_actions: list[ItemActionDraft] = Field(
        default_factory=list, description="Ordered operations; use this OR item_action, never both."
    )


class StageTurn(ActorTurnDraft):
    """One turn stage/validation.py already accepted, with the facts the engine derived.

    Identity, witnesses and provenance are derived, never authored: an actor proposes an
    ActorTurnDraft and the engine mints the rest once the turn holds.
    """

    # From here on addressed_to holds character IDs: normalize_turn resolves the names the actor
    # wrote, so the log never depends on how a model spelled someone.
    id: str
    scene_id: ModelId
    number: int = Field(ge=1)
    actor_id: ModelId
    # "world" marks what the stage itself does when the director unsticks a scene. It carries an
    # actor_id only so the cast it was witnessed by stays derivable; nobody performed it.
    kind: Literal["actor", "world"] = "actor"
    # Widened back to a plain string: a world event tries no tactic, and 7.0 logs used free text.
    tactic: str = ""
    beat_index: int = Field(ge=0)
    beat_event_id: str = ""
    witnesses: list[str] = Field(default_factory=list)
    direction_note: str = ""
    retrieved_memory_ids: list[str] = Field(default_factory=list)
    attempts: int = Field(default=1, ge=1)
    # None in every run without an inventory, and in a turn that handled no object.
    item_action: ItemAction | None = None
    item_actions: list[ItemAction] = Field(default_factory=list)
    # The form faults the engine fixed instead of bouncing the turn (7.9): the rejection code
    # each one would have raised. Empty in earlier logs, which never repaired.
    repairs: list[str] = Field(default_factory=list)


class TurnRejection(BaseModel):
    """Why one proposed turn could not be accepted, and what the actor was told to fix."""

    scene_id: ModelId
    actor_id: ModelId
    attempt: int = Field(ge=1)
    code: Literal[
        "EMPTY_TURN",
        "INTERNAL_IDENTIFIERS",
        "LONG_SPEECH",
        "FIRST_PERSON_ACTION",
        "REPEATED_LINE",
        "REPEATED_ACTION",
        "RESTATED_POSITION",
        "ACTOR_CALL_FAILED",
        "INVALID_WHISPER",
        "OUT_OF_FICTION",
        "UNKNOWN_ITEM",
        "ITEM_NOT_HELD",
        "ITEM_OUT_OF_REACH",
        "INVALID_ITEM_TARGET",
        "UNDECLARED_ITEM_ACTION",
        "INVALID_STATE_EVIDENCE",
        "TACTIC_RUN",
        "WRONG_LANGUAGE",
        "SPATIAL_CONTINUITY",
    ]
    issue: str
    turn: dict | None = None


class BeatDirection(BaseModel):
    """How the director opens one beat: who starts, and what each of them is playing for."""

    model_config = ConfigDict(extra="forbid")

    opening_actor_id: str = Field(description="Character ID of whoever speaks or acts first.")
    notes: list[str] = Field(
        default_factory=list,
        max_length=2,
        description=(
            "In the fiction language: at most two playable notes, each naming the character it "
            "is for, in the form 'ana: apriétale hasta que diga la fecha'. Never quote a line to "
            "be spoken."
        ),
    )
    objectives: list[str] = Field(
        default_factory=list,
        description=(
            "In the fiction language: one entry per character on stage, in the form "
            "'name: what they want right now', restating their scene objective as something "
            "they can play. Never a fact that character does not know."
        ),
    )
