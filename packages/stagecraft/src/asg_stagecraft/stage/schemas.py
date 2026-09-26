"""Data contracts for the casting, performance and narration stages.

Two kinds of model live here, and the split is the same one graph.py and script/validation.py
make: a ``*Draft`` is what a model proposed and Pydantic accepted, while the type without the
suffix is what this package's own validation already judged. Only the validators in this
subpackage mint the latter, so a signature asking for one cannot be handed raw model output.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..formats import ActorMemory, NarrativeVoice
from ..schemas import ID_PATTERN

# What a character contributes in one turn, and who is allowed to perceive it.
TurnVisibility = Literal["public", "whisper"]

# Where one memory record came from. The distinction matters for the knowledge boundary:
# "observed" is something the character saw someone else do, "own_turn" is what it did itself,
# and "thought" never leaves the character who thought it.
MemoryKind = Literal["initial", "observed", "own_turn", "thought", "stage_event", "reflection"]


class SceneCastBrief(BaseModel):
    """One character on stage in a scene, with the objective the script gives them there."""

    character_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    objective: str = Field(min_length=1)


class BeatBrief(BaseModel):
    """One plan event the scene must reach, as the director sees it.

    The actors never receive this: they are told a situation, an objective and a note. The beat
    is the director's own yardstick for whether the scene may move on.
    """

    event_id: str = Field(pattern=ID_PATTERN)
    title: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    promise_brief: str = ""


class SceneBrief(BaseModel):
    """Everything one scene of the performance is built from, persisted for the audit."""

    scene_id: str = Field(pattern=ID_PATTERN)
    number: int = Field(ge=1)
    chapter_id: str = Field(pattern=ID_PATTERN)
    act_number: int = Field(ge=1)
    location_id: str | None = None
    location_name: str = ""
    setting: str = Field(min_length=1)
    cast: list[SceneCastBrief] = Field(min_length=1)
    beats: list[BeatBrief] = Field(min_length=1)
    gate_facts: list[str] = Field(default_factory=list)
    scripted_lines: list[str] = Field(default_factory=list)


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
        description="In English: physical habits an audience can see. At most three.",
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
            "In English: what this character already knows when the curtain rises. This is their "
            "knowledge boundary at the start: anything absent here they must learn on stage."
        ),
    )
    relationships: list[ActorRelationship] = Field(default_factory=list)
    initial_emotion: str = Field(
        default="",
        description="In English: one word for how they feel when the story opens.",
    )
    initial_goal: str = Field(
        default="",
        description="In English: the immediate thing they are trying to do when the story opens.",
    )


class KnowledgeGate(BaseModel):
    """One fact some characters know and others do not, and the event that may reveal it.

    This is the information asymmetry the performance runs on. Only the director reads the
    gates; each actor is handed just the facts it is inside ``known_by`` for, which is how a
    secret stays a secret without asking a model to keep one.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERN)
    fact: str = Field(min_length=1, description="In English: the fact itself, stated plainly.")
    known_by: list[str] = Field(
        default_factory=list,
        description="Character IDs who already know this fact when the story opens.",
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


# --------------------------------------------------------------------------------------
# The performance
# --------------------------------------------------------------------------------------


class ActorTurnDraft(BaseModel):
    """One turn as the actor proposed it, before stage/validation.py has judged it."""

    model_config = ConfigDict(extra="forbid")

    thought: str = Field(
        default="",
        description=(
            "In the fiction language: what the character thinks and does not say. Nobody else "
            "ever perceives this. Leave empty when they are not thinking anything worth recording."
        ),
    )
    action: str = Field(
        default="",
        description=(
            "In the fiction language: what the character visibly does, as an audience would see "
            "it. No thoughts, no backstory. Empty when they only speak."
        ),
    )
    speech: str = Field(
        default="",
        description=(
            "In the fiction language: exactly the words the character says, with no quotation "
            "marks and no name prefix. Empty when they only act."
        ),
    )
    addressed_to: list[str] = Field(
        default_factory=list,
        description=(
            "Character IDs this turn is directed at. Empty when addressed to everyone present."
        ),
    )
    visibility: TurnVisibility = Field(
        default="public",
        description=(
            "'public' when everyone on stage perceives it, 'whisper' when only addressed_to do. "
            "A whisper needs addressed_to."
        ),
    )
    tactic: str = Field(
        default="",
        description=(
            "In English: the one-word or two-word move being tried, such as 'bluff' or 'plead'."
        ),
    )


class StageTurn(ActorTurnDraft):
    """One turn stage/validation.py already accepted, with the facts the engine derived.

    Identity, witnesses and provenance are derived, never authored: an actor proposes an
    ActorTurnDraft and the engine mints the rest once the turn holds.
    """

    id: str
    scene_id: str = Field(pattern=ID_PATTERN)
    number: int = Field(ge=1)
    actor_id: str = Field(pattern=ID_PATTERN)
    # "world" marks what the stage itself does when the director unsticks a scene. It carries an
    # actor_id only so the cast it was witnessed by stays derivable; nobody performed it.
    kind: Literal["actor", "world"] = "actor"
    beat_index: int = Field(ge=0)
    beat_event_id: str = ""
    witnesses: list[str] = Field(default_factory=list)
    direction_note: str = ""
    retrieved_memory_ids: list[str] = Field(default_factory=list)
    attempts: int = Field(default=1, ge=1)


class TurnRejection(BaseModel):
    """Why one proposed turn could not be accepted, and what the actor was told to fix."""

    scene_id: str = Field(pattern=ID_PATTERN)
    actor_id: str = Field(pattern=ID_PATTERN)
    attempt: int = Field(ge=1)
    code: Literal[
        "EMPTY_TURN",
        "INTERNAL_IDENTIFIERS",
        "MULTIPLE_BEATS",
        "REPEATED_LINE",
        "ACTOR_CALL_FAILED",
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
            "In English: at most two playable notes, each naming the character it is for, in the "
            "form 'ana: press him until he names the date'. Never quote a line to be spoken."
        ),
    )


class BeatCheckDraft(BaseModel):
    """The director's verdict on whether a beat has been reached, as proposed."""

    model_config = ConfigDict(extra="forbid")

    achieved: bool = Field(
        description="True only when the beat's outcome has actually happened on stage."
    )
    evidence: list[str] = Field(
        default_factory=list,
        description=(
            "Turn IDs from the transcript that show it happened. Required when achieved is true."
        ),
    )
    missing: str = Field(
        default="",
        description="In English: what still has to happen. Required when achieved is false.",
    )
    next_actor_id: str = Field(
        default="",
        description="Character ID who should move next, or empty to let the scene decide.",
    )
    notes: list[str] = Field(
        default_factory=list,
        max_length=2,
        description="In English: at most two playable notes, as in BeatDirection.",
    )
    stage_event: str = Field(
        default="",
        description=(
            "In the fiction language: something the world itself does that an audience can see or "
            "hear, used only when the scene has stalled. Empty otherwise."
        ),
    )


class BeatRecord(BaseModel):
    """What happened to one beat: the direction, every check, and how it closed."""

    event_id: str = Field(pattern=ID_PATTERN)
    index: int = Field(ge=0)
    opening_actor_id: str = ""
    notes: list[str] = Field(default_factory=list)
    checks: int = Field(default=0, ge=0)
    turns: int = Field(default=0, ge=0)
    achieved: bool = False
    forced: bool = False
    evidence: list[str] = Field(default_factory=list)
    stage_events: list[str] = Field(default_factory=list)


class RelationshipState(BaseModel):
    """One character's current standing towards another, replaced rather than accumulated.

    Consolidating instead of appending is deliberate: a log that records "allies" and then
    "enemies" without resolving them leaves an actor holding both at once, and it starts acting
    incoherently. The history stays in the memory records; the state is what the actor reads.
    """

    character_id: str = Field(pattern=ID_PATTERN)
    stance: str = Field(min_length=1)
    reason: str = ""


class CharacterState(BaseModel):
    """One character's evolving state, written by their own reflection at each scene's end."""

    character_id: str = Field(pattern=ID_PATTERN)
    scene_number: int = Field(ge=0)
    emotion: str = ""
    goal: str = ""
    relationships: list[RelationshipState] = Field(default_factory=list)


class MemoryRecord(BaseModel):
    """One entry in a character's own memory stream.

    ``importance`` is the character's own sense of how much a moment mattered, which is what the
    retrieval scoring uses; it is never shown to any agent as a number.
    """

    id: str
    character_id: str = Field(pattern=ID_PATTERN)
    kind: MemoryKind
    scene_number: int = Field(ge=0)
    turn_id: str = ""
    text: str = Field(min_length=1)
    participants: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryRetrieval(BaseModel):
    """One retrieval, with the score breakdown that produced it, kept for the audit."""

    character_id: str = Field(pattern=ID_PATTERN)
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
        default="", description="In English: one word for how I feel leaving this scene."
    )
    goal: str = Field(default="", description="In English: what I am trying to do next.")
    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How much this scene mattered to me, from 0 for routine to 1 for life-changing."
        ),
    )


class ScenePerformance(BaseModel):
    """One performed scene: its turns, its beats and what each actor took away."""

    scene_id: str = Field(pattern=ID_PATTERN)
    number: int = Field(ge=1)
    chapter_id: str = Field(pattern=ID_PATTERN)
    turns: list[StageTurn] = Field(default_factory=list)
    beats: list[BeatRecord] = Field(default_factory=list)
    rejected: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)


class PerformanceSettings(BaseModel):
    """The exact knobs one performance ran with, so a reader can repeat or compare it."""

    actor_memory: ActorMemory
    turns_per_beat: int = Field(ge=2)
    check_every: int = Field(ge=1)
    retrieved_records: int = Field(ge=1)
    recency_decay: float = Field(ge=0.0)
    repetition_threshold: float = Field(ge=0.0, le=1.0)


class PerformanceArtifact(BaseModel):
    """The complete performance contract: performance.json.

    A documented JSON contract like script.json: every field is meant to be read from the file,
    so an analysis script never has to import this package to study a run.
    """

    contract_version: str = "1"
    language: str
    settings: PerformanceSettings
    scenes: list[ScenePerformance] = Field(default_factory=list)
    states: list[CharacterState] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------------------
# Narration
# --------------------------------------------------------------------------------------


class ChapterNarration(BaseModel):
    """One narrated chapter and the performed material it was written from."""

    chapter_id: str = Field(pattern=ID_PATTERN)
    chapter_index: int = Field(ge=1)
    scene_ids: list[str] = Field(default_factory=list)
    turns_available: int = Field(ge=0)
    turns_visible: int = Field(ge=0)
    words: int = Field(ge=0)
    attempts: int = Field(ge=1)
    source: Literal["narrator", "fallback"]


class NarrationArtifact(BaseModel):
    """How the prose was narrated from the log: the voice, the narrator, and every chapter."""

    contract_version: str = "1"
    narrative_voice: NarrativeVoice
    narrator_character_id: str = ""
    chapters: list[ChapterNarration] = Field(default_factory=list)
