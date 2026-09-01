"""Top-Down public API."""

from .generator import StoryGenerator, StoryRun
from .profiles import NarrativeProfile
from .progress import (
    PipelineEvent,
    PipelineEventCallback,
    ProgressCallback,
    ProgressUpdate,
    format_progress,
)
from .schemas import (
    ChapterMetrics,
    ChapterPlan,
    ChapterPresentation,
    ChapterRevisionAttempt,
    ChapterRevisionResult,
    CharactersArtifact,
    EventDependency,
    GeneratorVersionArtifact,
    PlanReview,
    PlotEvent,
    RevisionReport,
    StoryMetrics,
    StoryPlan,
    StoryPresentation,
    StoryRequest,
    StoryReview,
    WorldArtifact,
    WriterCandidateDiagnostic,
)
from .version import __version__

__all__ = [
    "ChapterMetrics",
    "ChapterPlan",
    "ChapterPresentation",
    "ChapterRevisionAttempt",
    "ChapterRevisionResult",
    "CharactersArtifact",
    "EventDependency",
    "GeneratorVersionArtifact",
    "NarrativeProfile",
    "PlanReview",
    "PipelineEvent",
    "PipelineEventCallback",
    "PlotEvent",
    "ProgressCallback",
    "ProgressUpdate",
    "RevisionReport",
    "StoryGenerator",
    "StoryMetrics",
    "StoryPlan",
    "StoryPresentation",
    "StoryRequest",
    "StoryReview",
    "StoryRun",
    "WorldArtifact",
    "WriterCandidateDiagnostic",
    "__version__",
    "format_progress",
]
