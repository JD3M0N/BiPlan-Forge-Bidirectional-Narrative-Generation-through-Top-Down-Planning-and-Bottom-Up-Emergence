"""The frozen plan: chapters, plot events and the dependencies between them."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)

from ..planning.catalog_types import ModelId


class ChapterDraft(BaseModel):
    """One chapter as the planner proposed it, before graph.py has judged the plan."""

    id: ModelId
    order: int = Field(ge=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    dramatic_goal: str = Field(min_length=1)
    opening_state: str = Field(min_length=1)
    turning_point: str = Field(min_length=1)
    closing_state: str = Field(min_length=1)


class ChapterPlan(ChapterDraft):
    """One chapter of a plan materialize_plan already validated.

    The fields match ChapterDraft deliberately: what separates the two is provenance,
    not shape. Only graph.py mints a ChapterPlan, and it does so after the invariants
    hold, so a signature asking for one cannot be handed raw model output. This mirrors
    the StoryPlanDraft/StoryPlan split at the level of a single chapter; collapsing it
    would let unvalidated chapters reach the drafter and the audit.
    """


class PlotEvent(BaseModel):
    """Represent PlotEvent data and behavior."""

    id: ModelId
    order: int = Field(ge=1)
    chapter_id: ModelId
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    dramatic_function: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    preconditions: list[str] = Field(
        default_factory=list,
        description="Plain-English story-state conditions, not entity or event IDs.",
    )
    character_ids: list[str] = Field(default_factory=list)
    location_id: str | None = None
    object_ids: list[str] = Field(
        default_factory=list,
        description="Canonical StoryObject IDs used in this event.",
    )
    effects: list[str] = Field(
        min_length=1,
        description="Plain-English story-state changes caused by this event, not IDs.",
    )
    payoff_of: list[str] = Field(
        default_factory=list,
        description=(
            "PlotEvent IDs for setups paid off by this event. Every value must be the ID "
            "of an earlier event; never use object, character, location, or prose values. "
            "Use an empty list when this event pays off no earlier event."
        ),
    )


class EventDependency(BaseModel):
    """Represent EventDependency data and behavior."""

    source_event_id: ModelId
    target_event_id: ModelId
    relation: Literal["causal", "temporal"]


class StoryPlanDraft(BaseModel):
    """Represent StoryPlanDraft data and behavior."""

    logline: str
    theme: str
    ending: str
    narrative_structure: str = Field(min_length=1)
    dramatic_question: str = Field(min_length=1)
    stakes: str = Field(min_length=1)
    chapters: list[ChapterDraft] = Field(min_length=1)
    events: list[PlotEvent] = Field(min_length=1)
    dependencies: list[EventDependency] = Field(default_factory=list)


class StoryPlan(BaseModel):
    """Represent StoryPlan data and behavior."""

    logline: str
    theme: str
    ending: str
    narrative_structure: str = Field(min_length=1)
    dramatic_question: str = Field(min_length=1)
    stakes: str = Field(min_length=1)
    chapters: list[ChapterPlan] = Field(min_length=1)
    events: list[PlotEvent] = Field(min_length=1)
    dependencies: list[EventDependency] = Field(default_factory=list)
    topological_order: list[str] = Field(default_factory=list)
