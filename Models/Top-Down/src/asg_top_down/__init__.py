"""Generación automática de historias mediante planificación Top-Down."""

from .generator import StoryGenerator, StoryRun
from .incremental import IncrementalPlotPlanner, StorylineState
from .narrative_db import (
    NarrativeBlueprint, NarrativeSchemaRepository, TaxonomyCandidate, TaxonomyProfile,
)
from .craft import build_storyline_obligations
from .schemas import (
    ChapterPPPPlan, ChapterWritingBrief, CharacterArcPlan, GlobalPPPPlan,
    StorylineObligationsArtifact, TaxonomyApplication, TaxonomyBrief, TryFailPlan,
)
from .progress import ProgressCallback, ProgressUpdate, format_progress

__all__ = [
    "ProgressCallback",
    "ProgressUpdate",
    "StoryGenerator",
    "StoryRun",
    "IncrementalPlotPlanner",
    "StorylineState",
    "NarrativeBlueprint",
    "NarrativeSchemaRepository",
    "TaxonomyProfile",
    "TaxonomyCandidate",
    "TaxonomyApplication",
    "TaxonomyBrief",
    "GlobalPPPPlan",
    "ChapterPPPPlan",
    "CharacterArcPlan",
    "TryFailPlan",
    "StorylineObligationsArtifact",
    "ChapterWritingBrief",
    "build_storyline_obligations",
    "format_progress",
]
