"""The promise ledger a story opens, develops and has to pay off."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)

from ..planning.catalog_types import ID_PATTERN, ModelId

PromiseKind = Literal["story_direction", "character_conflict", "genre_structure", "tone"]


class PromiseBeat(BaseModel):
    """One ledger beat anchored to an event the validated plan already contains.

    The anchor is the whole point of the contract: a beat cites a PlotEvent ID instead of
    describing a moment of its own, so the ledger can annotate the frozen storyline without
    ever being able to ask for a new one.
    """

    event_id: str = Field(
        pattern=ID_PATTERN,
        description="ID of a PlotEvent the validated plan already contains.",
    )


class PromiseOpening(PromiseBeat):
    """The event where one promise becomes visible to the reader."""

    signal: str = Field(min_length=1)
    reader_expectation: str = Field(min_length=1)


class PromiseProgress(PromiseBeat):
    """One signposted advance that keeps a promise alive between opening and payoff."""

    id: ModelId
    observable_delta: str = Field(min_length=1)
    new_cost_or_information: str = Field(min_length=1)


class PromisePayoff(PromiseBeat):
    """The event that answers one promise, and the preparation that earned the answer."""

    answer: str = Field(min_length=1)
    cost: str = Field(min_length=1)
    prepared_by_progress_ids: list[str] = Field(min_length=1)
    surprising_without_breach: str = Field(min_length=1)


class PromiseContract(BaseModel):
    """One expectation the story opens, signposts, and pays off."""

    id: ModelId
    kind: PromiseKind
    subject: str = Field(min_length=1)
    dramatic_question: str = Field(min_length=1)
    opening: PromiseOpening
    progress: list[PromiseProgress] = Field(min_length=1)
    payoff: PromisePayoff


class PromiseLedgerDraft(BaseModel):
    """A promise ledger as the model proposed it, before promises.py has judged it."""

    primary_promise_id: ModelId
    promises: list[PromiseContract] = Field(min_length=2, max_length=8)


class PromiseLedger(PromiseLedgerDraft):
    """A ledger materialize_ledger already checked against the frozen plan.

    The fields it adds are all derived, never authored: chapter_by_event resolves each anchor
    through the plan, observations record non-blocking findings, and the prompt blocks keep the
    exact text that travelled to the model so a run stays auditable.
    """

    chapter_by_event: dict[str, str] = Field(default_factory=dict)
    observations: list[str] = Field(default_factory=list)
    chapter_blocks: dict[str, str] = Field(default_factory=dict)
    critic_block: str = ""


class PromiseCheck(BaseModel):
    """One critic verdict on whether the draft honored a promise of the ledger."""

    promise_id: ModelId
    opened: bool
    progressed: bool
    paid: bool
    verdict: Literal["fulfilled", "weak", "broken"]
    evidence: str = Field(min_length=1)


class PromiseAuditEntry(BaseModel):
    """One promise of the ledger next to the verdict the critic returned for it."""

    promise_id: ModelId
    kind: PromiseKind
    primary: bool
    verdict: Literal["fulfilled", "weak", "broken"]
    opened: bool
    progressed: bool
    paid: bool
    evidence: str = ""
    supporting_turn_ids: list[str] = Field(default_factory=list)


class PromiseAuditArtifact(BaseModel):
    """Observed promise fulfillment for one run, never a target handed to any agent."""

    source: Literal["script", "performance", "narration"] = "script"
    promises: int = Field(default=0, ge=0)
    fulfilled: int = Field(default=0, ge=0)
    weak: int = Field(default=0, ge=0)
    broken: int = Field(default=0, ge=0)
    fulfilled_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    entries: list[PromiseAuditEntry] = Field(default_factory=list)
