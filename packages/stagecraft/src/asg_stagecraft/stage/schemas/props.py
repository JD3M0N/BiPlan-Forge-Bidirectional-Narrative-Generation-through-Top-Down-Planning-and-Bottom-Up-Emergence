"""The optional inventory: the objects on stage and the moves allowed on them."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...schemas import ModelId
from .vocabulary import ItemVerb

# --------------------------------------------------------------------------------------
# Props and the inventory
# --------------------------------------------------------------------------------------


class PropDraft(BaseModel):
    """One object on stage as the prop master placed it, before stage/props.py judged it."""

    model_config = ConfigDict(extra="forbid")

    object_id: str = Field(
        default="",
        description=(
            "The world object ID this prop is, when it is one of the objects listed under "
            "WORLD. Empty for a personal object you are adding."
        ),
    )
    name: str = Field(
        min_length=1,
        description=(
            "In the fiction language: what the characters call this object, as it would be "
            "named on stage. This is the only handle an actor ever gets for it."
        ),
    )
    appearance: str = Field(
        default="",
        description=(
            "In the fiction language: what anyone who sees it can tell at a glance, in a "
            "clause. Empty when the name says everything."
        ),
    )
    holder_id: str = Field(
        default="",
        description=(
            "Character ID of whoever carries it when the curtain rises. Empty when it is not "
            "on anyone, and then it lies in a location."
        ),
    )
    location_id: str = Field(
        default="",
        description=(
            "World location ID where it lies when nobody carries it. Ignored when holder_id is set."
        ),
    )
    concealed: bool = Field(
        default=False,
        description=(
            "True when its holder keeps it out of sight, so the others cannot see or take it "
            "until it is shown. Only an object with a holder can be concealed."
        ),
    )


class PropListDraft(BaseModel):
    """Every object the performance may handle, as the prop master proposed it."""

    props: list[PropDraft] = Field(default_factory=list)


class Prop(PropDraft):
    """One object stage/props.py accepted, with the identity the arbiter tracks it by."""

    # Minted here, never authored: a world object keeps its own ID and a personal one is
    # numbered, so two props can share a name and still be told apart in the log.
    id: ModelId


class PropList(BaseModel):
    """The dressed stage: props.json.

    What the arbiter starts from. Holder and location are the opening truth only; from the
    first turn on, StageInventory owns where each prop is.
    """

    props: list[Prop] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    fallback: bool = False


class ItemActionDraft(BaseModel):
    """What an actor proposes to do with an object this turn, by name."""

    model_config = ConfigDict(extra="forbid")

    verb: ItemVerb = Field(
        default="none",
        description=(
            "'none' for a turn that handles no object - most turns. 'use' to put one to work, "
            "'give' to hand it to someone, 'take' to pick one up or take it off someone, "
            "'drop' to leave it, 'hide' to put yours out of sight, 'show' to bring it back "
            "into view."
        ),
    )
    item: str = Field(
        default="",
        description=(
            "The name of the object, as it appears under LO QUE LLEVAS or LO QUE VES. Empty "
            "only when verb is 'none'."
        ),
    )
    target: str = Field(
        default="",
        description=(
            "For 'give', the name of whoever receives it, as listed under CONTIGO EN ESCENA. "
            "For 'take', whoever you take it from, when you take it off someone. Empty "
            "otherwise."
        ),
    )


class ItemAction(BaseModel):
    """One object move the arbiter accepted, resolved to identities and witnesses.

    What the actor wrote was names; what the log keeps is IDs, exactly as with addressed_to.
    ``item_name`` rides along so a reader, a prompt or a narrator never has to join this
    against props.json.
    """

    verb: ItemVerb
    item_id: ModelId
    item_name: str = Field(min_length=1)
    performer_id: str = ""
    target_id: str = ""
    # Whoever held the object before this move: the giver, or whoever it was taken from.
    from_id: str = ""
    witnesses: list[str] = Field(default_factory=list)
