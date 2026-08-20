"""Post-STORYLINE story-craft contracts for Top-Down 4.0."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .domain import ArcType, CharacterWritingCard


PromiseKind = Literal["story_direction", "character_conflict", "genre_structure"]
ProgressMode = Literal["advance", "complicate", "reframe"]
ArcEvidenceStage = Literal["establishment", "pressure", "decisive_choice", "consequence"]
TryFailOutcome = Literal["yes_but", "no_and", "final_resolution"]


class ToneContract(BaseModel):
    description: str = Field(min_length=1)
    opening_signal: str = Field(min_length=1)
    continuity_rule: str = Field(min_length=1)
    closing_echo: str = Field(min_length=1)


class PromiseOpening(BaseModel):
    id: str = Field(min_length=1)
    chapter_id: str
    signal: str = Field(min_length=1)
    reader_effect: str = Field(min_length=1)


class PromiseProgress(BaseModel):
    id: str = Field(min_length=1)
    chapter_id: str
    mode: ProgressMode
    observable_delta: str = Field(min_length=1)
    new_cost_or_information: str = Field(min_length=1)
    reader_effect: str = Field(min_length=1)


class PromisePayoff(BaseModel):
    id: str = Field(min_length=1)
    chapter_id: str
    answer: str = Field(min_length=1)
    cost: str = Field(min_length=1)
    prepared_by_progress_ids: list[str] = Field(min_length=1)
    surprising_without_breach: str = Field(min_length=1)


class PromiseContract(BaseModel):
    id: str = Field(min_length=1)
    kind: PromiseKind
    subject: str = Field(min_length=1)
    expectation: str = Field(min_length=1)
    dramatic_question: str = Field(min_length=1)
    fulfillment_criteria: list[str] = Field(min_length=1)
    opening: PromiseOpening
    progress: list[PromiseProgress] = Field(min_length=1)
    payoff: PromisePayoff

    @model_validator(mode="after")
    def local_ids_are_unique_and_preparation_exists(self) -> "PromiseContract":
        ids = [self.opening.id, *(item.id for item in self.progress), self.payoff.id]
        if len(ids) != len(set(ids)):
            raise ValueError("promise beat ids must be unique")
        progress_ids = {item.id for item in self.progress}
        unknown = set(self.payoff.prepared_by_progress_ids) - progress_ids
        if unknown:
            raise ValueError(f"payoff preparation references unknown progress: {sorted(unknown)}")
        return self


class PromiseLedger(BaseModel):
    tone: ToneContract
    primary_promise_id: str
    promises: list[PromiseContract] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def ledger_ids_are_unique(self) -> "PromiseLedger":
        promise_ids = [item.id for item in self.promises]
        beat_ids = [
            beat_id for item in self.promises
            for beat_id in [item.opening.id, *(beat.id for beat in item.progress), item.payoff.id]
        ]
        if len(promise_ids) != len(set(promise_ids)):
            raise ValueError("promise ids must be unique")
        if len(beat_ids) != len(set(beat_ids)):
            raise ValueError("promise beat ids must be globally unique")
        if self.primary_promise_id not in set(promise_ids):
            raise ValueError("primary_promise_id must identify a supplied promise")
        return self


class CharacterArcEvidence(BaseModel):
    id: str = Field(min_length=1)
    chapter_id: str
    stage: ArcEvidenceStage
    behavior: str = Field(min_length=1)
    choice_or_cost: str = Field(min_length=1)


class PlannedCharacterArc(BaseModel):
    character_id: str
    arc_type: ArcType
    focus_description: str = Field(min_length=1)
    evidences: list[CharacterArcEvidence] = Field(min_length=4, max_length=4)
    enables_or_prevents_promise_id: str = Field(min_length=1)
    decisive_choice_uses_want: str = Field(min_length=1)
    decisive_choice_uses_need: str = Field(min_length=1)
    external_payoff_effect: Literal["enables", "prevents"]
    internal_to_external_rationale: str = Field(min_length=1)


class CharacterArcPlan(BaseModel):
    arcs: list[PlannedCharacterArc] = Field(min_length=1)


class TryFailCycle(BaseModel):
    id: str = Field(min_length=1)
    chapter_id: str
    promise_id: str
    action: str = Field(min_length=1)
    outcome: Literal["yes_but", "no_and"]
    consequence: str = Field(min_length=1)
    lesson: str = Field(min_length=1)
    stakes_change: str = Field(min_length=1)


class TryFailPlan(BaseModel):
    cycles: list[TryFailCycle] = Field(min_length=1)


class CraftAlignmentEntry(BaseModel):
    craft_id: str
    chapter_id: str
    node_ids: list[str] = Field(min_length=1)


class CraftAlignment(BaseModel):
    entries: list[CraftAlignmentEntry] = Field(min_length=1)


class SceneCraftDirective(BaseModel):
    node_id: str
    goal: str = Field(min_length=1)
    conflict: str = Field(min_length=1)
    outcome: TryFailOutcome
    consequence: str = Field(min_length=1)
    reaction: str = Field(min_length=1)
    dilemma: str = Field(min_length=1)
    decision: str = Field(min_length=1)


class ChapterCraftView(BaseModel):
    chapter_id: str
    opened_promise_ids: list[str] = Field(default_factory=list)
    progressed_promise_ids: list[str] = Field(default_factory=list)
    paid_promise_ids: list[str] = Field(default_factory=list)
    scene_directives: list[SceneCraftDirective] = Field(default_factory=list)

    @model_validator(mode="after")
    def acts_on_a_promise(self) -> "ChapterCraftView":
        if not (self.opened_promise_ids or self.progressed_promise_ids or self.paid_promise_ids):
            raise ValueError("every chapter must act on at least one active promise")
        return self


class CraftComposition(BaseModel):
    alignment: CraftAlignment
    chapters: list[ChapterCraftView] = Field(min_length=1)


class PromiseActionBrief(BaseModel):
    phase: Literal["open", "progress", "payoff"]
    subject: str
    instruction: str


class SceneWritingDirective(BaseModel):
    event: str
    goal: str
    conflict: str
    outcome: TryFailOutcome
    consequence: str
    reaction_dilemma_decision: str


class PlannedMutationBrief(BaseModel):
    entity: str
    change: str
    value: str


class FactualEventBrief(BaseModel):
    event: str
    intention: str
    conflict: str
    consequence: str
    location: str
    planned_changes: list[PlannedMutationBrief] = Field(default_factory=list)


class EntityStateBrief(BaseModel):
    entity: str
    kind: str
    state: dict[str, str] = Field(default_factory=dict)
    knowledge: list[str] = Field(default_factory=list)


class ChapterWritingBrief(BaseModel):
    tone_guidance: str
    factual_events: list[FactualEventBrief] = Field(min_length=1)
    state_before: list[EntityStateBrief] = Field(default_factory=list)
    promise_actions: list[PromiseActionBrief] = Field(min_length=1)
    scene_directives: list[SceneWritingDirective] = Field(default_factory=list)
    character_cards: list[CharacterWritingCard] = Field(default_factory=list)
    arc_behaviors: list[str] = Field(default_factory=list)


class StoryCraftPlan(BaseModel):
    promise_ledger: PromiseLedger
    character_arcs: CharacterArcPlan
    try_fail: TryFailPlan
    alignment: CraftAlignment
    chapters: list[ChapterCraftView] = Field(min_length=1)
