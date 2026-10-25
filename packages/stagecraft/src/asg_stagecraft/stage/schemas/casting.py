"""Who is on stage: dossiers, relationships and the gates that hold their secrets."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...schemas import ModelId
from .vocabulary import GateReveal

# --------------------------------------------------------------------------------------
# Casting
# --------------------------------------------------------------------------------------


class ActorRelationship(BaseModel):
    """How one character stands towards another when the curtain rises."""

    character_id: str = Field(description="Character ID of the other character.")
    stance: str = Field(
        min_length=1, description="In English: the standing attitude, in a word or two."
    )
    wants_from_them: str = Field(
        min_length=1, description="In English: what this character wants from them."
    )
    history: str = Field(
        default="", description="In English: the shared past that explains the stance."
    )
    private_opinion: str = Field(
        default="",
        description="In English: what this character thinks of them but would not say aloud.",
    )


class ActorDossier(BaseModel):
    """One character as an actor receives them: playable wants, rules and a knowledge boundary.

    Every field is a behavioral instruction rather than a portrait, which is the finding of the
    role-playing literature: an actor plays "always deflects a direct question" far better than
    "is evasive". Written in English like characters.json, and never printed for a reader.
    """

    model_config = ConfigDict(extra="forbid")

    character_id: str = Field(description="Character ID from characters.json.")
    public_face: str = Field(
        default="",
        description=(
            "In the fiction language: what anyone who sees this character can tell at a glance - "
            "apparent gender and age, their trade if it is public, one visible trait. This is "
            "the only thing the others know about them before they speak."
        ),
    )
    want: str = Field(
        min_length=1,
        description=(
            "In English: the concrete, pursuable thing this character is after in the story."
        ),
    )
    need: str = Field(
        default="",
        description="In English: what they actually need, which they may not know they need.",
    )
    wound: str = Field(
        default="", description="In English: the past injury that still shapes them."
    )
    fear: str = Field(
        default="", description="In English: what they are most afraid of losing or facing."
    )
    moral_line: str = Field(
        default="",
        description="In English: the thing they will not do, and what it would cost them to do it.",
    )
    secret: str = Field(
        default="", description="In English: what they are hiding. Empty when nothing."
    )
    secret_from: list[str] = Field(
        default_factory=list,
        description=(
            "Character IDs this secret is kept from. Empty when the secret is kept from nobody."
        ),
    )
    voice: str = Field(
        min_length=1,
        description=(
            "In English: how they speak — register, rhythm, sentence length, what they never say. "
            "Concrete enough that another actor could imitate it."
        ),
    )
    mannerisms: list[str] = Field(
        default_factory=list,
        description=(
            "In English: physical habits that surface under pressure. At most three, and an "
            "actor uses them rarely, never twice in a row."
        ),
    )
    tactics: list[str] = Field(
        default_factory=list,
        description=(
            "In English: the moves they use to get what they want, strongest first "
            "(for example 'flatters, then threatens'). At most four."
        ),
    )
    triggers: list[str] = Field(
        default_factory=list,
        description="In English: 'When X happens, they Y.' Situation and reaction, at most three.",
    )
    behavior_rules: list[str] = Field(
        default_factory=list,
        description=(
            "In English: 'Always ...' or 'Never ...' rules that hold across the whole story."
        ),
    )
    initial_knowledge: list[str] = Field(
        default_factory=list,
        description=(
            "In the fiction language: what this character already knows when the curtain rises. "
            "This is their knowledge boundary at the start: anything absent here they must learn "
            "on stage. Never include what they will deduce or discover during the story."
        ),
    )
    knowledge_sources: list[str] = Field(
        default_factory=list,
        description=(
            "One entry per initial_knowledge fact, in the same order, saying where it comes "
            "from: 'world', 'backstory', or the id of the plan event it comes from."
        ),
    )
    cover_story: str = Field(
        default="",
        description=(
            "In the fiction language, only when this character has a secret: the version of "
            "events they tell instead, as something they would say. Empty otherwise."
        ),
    )
    relationships: list[ActorRelationship] = Field(default_factory=list)
    initial_emotion: str = Field(
        default="",
        description="In the fiction language: one word for how they feel when the story opens.",
    )
    initial_goal: str = Field(
        default="",
        description="In the fiction language: their immediate goal at the start.",
    )


class KnowledgeGate(BaseModel):
    """One fact some characters know and others do not, and the event that may reveal it.

    This is the information asymmetry the performance runs on. Only the director reads the
    gates; each actor is handed just the facts it is inside ``known_by`` for, which is how a
    secret stays a secret without asking a model to keep one.
    """

    model_config = ConfigDict(extra="forbid")

    id: ModelId
    premise_gate_ids: list[str] = Field(default_factory=list)
    initial_premises: list[str] = Field(default_factory=list)
    fact: str = Field(
        min_length=1,
        description="In the fiction language: the fact itself, stated plainly.",
    )
    known_by: list[str] = Field(
        default_factory=list,
        description=(
            "Character IDs who already know this fact BEFORE the first scene. Never the character "
            "who deduces or discovers it on stage: the culprit knows what they did, the detective "
            "does not know the answer."
        ),
    )
    revealed_by: str = Field(
        default="",
        description=(
            "Character ID of whoever brings this fact to light, or empty when the world or a "
            "piece of evidence reveals it."
        ),
    )
    how: GateReveal = Field(
        description=(
            "How it comes out: 'confession' (a holder admits it), 'deduction' or 'discovery' "
            "(someone who did not know works it out or finds it), 'told' or 'overheard'."
        ),
    )
    revealed_at_event_id: str = Field(
        default="",
        description=(
            "Plan event ID where this fact becomes known to everyone present, or empty when the "
            "story never reveals it."
        ),
    )


class CastBibleDraft(BaseModel):
    """The cast bible as the casting director proposed it, before casting.py has judged it."""

    dossiers: list[ActorDossier] = Field(min_length=1)
    knowledge_gates: list[KnowledgeGate] = Field(default_factory=list)


class CastBible(CastBibleDraft):
    """A cast bible validated against the frozen plan, the script's cast and characters.json."""

    observations: list[str] = Field(default_factory=list)
    fallback: bool = False
