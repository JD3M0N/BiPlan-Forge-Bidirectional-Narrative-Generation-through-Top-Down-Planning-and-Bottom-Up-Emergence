"""Data contracts for the casting, performance and narration stages.

Two kinds of model live here, and the split is the same one graph.py and script/validation.py
make: a ``*Draft`` is what a model proposed and Pydantic accepted, while the type without the
suffix is what this package's own validation already judged. Only the validators in this
subpackage mint the latter, so a signature asking for one cannot be handed raw model output.

The models are grouped by what they belong to; this module keeps the whole
contract importable from one place, as it was when they shared a single file.
"""

from .artifacts import (
    PerformanceArtifact,
    PerformanceSettings,
    PromiseStoryAuditDraft,
    PromiseStoryCheck,
    ScenePerformance,
)
from .briefs import (
    BeatBrief,
    FutureConflict,
    FutureRevision,
    RevisedBeat,
    RevisedScene,
    SceneBrief,
    SceneCastBrief,
)
from .casting import (
    ActorDossier,
    ActorRelationship,
    CastBible,
    CastBibleDraft,
    KnowledgeGate,
)
from .memory import (
    CharacterState,
    MemoryRecord,
    MemoryRetrieval,
    ReflectionDraft,
    RelationshipState,
)
from .narration import (
    ChapterNarration,
    ChapterSelection,
    NarrationArtifact,
    NarrationFinding,
    NarrationReview,
    ReportedLine,
    ReportedLines,
    SelectedMoment,
    WorldEventAssessment,
)
from .props import (
    ItemAction,
    ItemActionDraft,
    Prop,
    PropDraft,
    PropList,
    PropListDraft,
)
from .turns import (
    ActorTurnDraft,
    ActorTurnWithItemsDraft,
    BeatDirection,
    StageTurn,
    TurnRejection,
)
from .verdicts import (
    BeatCheckDraft,
    BeatEvidence,
    BeatRecord,
    DirectorEntry,
    EvidenceSource,
    FactProposal,
    OutcomePart,
    StageFact,
    TypedBeatCheckDraft,
    TypedOutcomePart,
    WorldItemDraft,
)
from .vocabulary import (
    TACTIC_NAMES,
    YIELDING_TACTICS,
    GateReveal,
    ItemVerb,
    MemoryKind,
    Tactic,
    TurnVisibility,
)

__all__ = [
    "ActorDossier",
    "ActorRelationship",
    "ActorTurnDraft",
    "ActorTurnWithItemsDraft",
    "BeatBrief",
    "BeatCheckDraft",
    "BeatDirection",
    "BeatEvidence",
    "BeatRecord",
    "CastBible",
    "CastBibleDraft",
    "ChapterNarration",
    "ChapterSelection",
    "CharacterState",
    "DirectorEntry",
    "EvidenceSource",
    "FactProposal",
    "FutureConflict",
    "FutureRevision",
    "GateReveal",
    "ItemAction",
    "ItemActionDraft",
    "ItemVerb",
    "KnowledgeGate",
    "MemoryKind",
    "MemoryRecord",
    "MemoryRetrieval",
    "NarrationArtifact",
    "NarrationFinding",
    "NarrationReview",
    "OutcomePart",
    "PerformanceArtifact",
    "PerformanceSettings",
    "PromiseStoryAuditDraft",
    "PromiseStoryCheck",
    "Prop",
    "PropDraft",
    "PropList",
    "PropListDraft",
    "ReflectionDraft",
    "RelationshipState",
    "ReportedLine",
    "ReportedLines",
    "RevisedBeat",
    "RevisedScene",
    "SceneBrief",
    "SceneCastBrief",
    "ScenePerformance",
    "SelectedMoment",
    "StageFact",
    "StageTurn",
    "TACTIC_NAMES",
    "Tactic",
    "TurnRejection",
    "TurnVisibility",
    "TypedBeatCheckDraft",
    "TypedOutcomePart",
    "WorldEventAssessment",
    "WorldItemDraft",
    "YIELDING_TACTICS",
]
