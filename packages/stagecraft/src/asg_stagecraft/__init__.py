"""Stagecraft public API."""

from .brief import CastMember, StoryBrief
from .generator import StoryGenerator, StoryRun
from .options import GenerationOptions
from .planning.profiles import NarrativeProfile
from .runtime.progress import PipelineEvent, ProgressUpdate, format_progress
from .schemas import (
    ChapterPlan,
    ChapterPresentation,
    CharactersArtifact,
    EventDependency,
    PlanReview,
    PlotEvent,
    StoryPlan,
    StoryPresentation,
    StoryRequest,
    StoryReview,
    WorldArtifact,
    WriterCandidateDiagnostic,
)
from .version import __version__

__all__ = [
    "CastMember",
    "ChapterPlan",
    "ChapterPresentation",
    "CharactersArtifact",
    "EventDependency",
    "GenerationOptions",
    "NarrativeProfile",
    "PipelineEvent",
    "PlanReview",
    "PlotEvent",
    "ProgressUpdate",
    "StoryBrief",
    "StoryGenerator",
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
