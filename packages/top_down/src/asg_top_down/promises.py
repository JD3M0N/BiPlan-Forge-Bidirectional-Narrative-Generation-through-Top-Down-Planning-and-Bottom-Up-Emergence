"""Deterministic validation of the Promise-Progress-Payoff ledger over a frozen plan.

Every ValueError message raised here stays in English on purpose, exactly as in graph.py:
pipeline.py reinjects it verbatim into the model's ledger-repair prompt, so it is part of the
contract with the model, not user-facing text.

The ledger never authors a beat. Each opening, progress and payoff cites the ID of a PlotEvent
the validated plan already contains, so the checks below are decided against
plan.topological_order instead of trusting what the model says about its own ordering.
"""

from __future__ import annotations

from operator import attrgetter

from .profiles import NarrativeProfile, promise_band
from .schemas import (
    PlotEvent,
    PromiseContract,
    PromiseLedger,
    PromiseLedgerDraft,
    StoryPlan,
)

PRIMARY_KIND = "story_direction"


def materialize_ledger(
    draft: PromiseLedgerDraft,
    plan: StoryPlan,
    profile: NarrativeProfile,
) -> PromiseLedger:
    """Validate a proposed ledger against the frozen plan and mint the trusted version."""
    positions = _event_positions(plan)
    chapter_by_event = {event.id: event.chapter_id for event in plan.events}
    last_chapter = max(plan.chapters, key=attrgetter("order")).id
    _validate_size(draft, profile)
    _validate_identifiers(draft)
    _validate_primary(draft)
    for promise in draft.promises:
        _validate_anchors(promise, positions)
        # Placement before order on purpose: a promise opened in the final chapter is the more
        # fundamental mistake, and reporting the span first would send the model to repair the
        # symptom instead of the cause.
        _validate_chapter_placement(promise, chapter_by_event, last_chapter, draft)
        _validate_beat_order(promise, positions)
        _validate_preparation(promise)
    return PromiseLedger(
        primary_promise_id=draft.primary_promise_id,
        promises=draft.promises,
        chapter_by_event={
            event_id: chapter_by_event[event_id] for event_id in _anchored_events(draft)
        },
        observations=ledger_observations(draft, plan),
    )


def ledger_observations(draft: PromiseLedgerDraft, plan: StoryPlan) -> list[str]:
    """Report non-blocking findings a valid ledger can still carry."""
    observations: list[str] = []
    seen: dict[tuple[str, str], str] = {}
    for promise in draft.promises:
        span = (promise.opening.event_id, promise.payoff.event_id)
        if span in seen:
            observations.append(
                f"promises {seen[span]} and {promise.id} open and pay off on the same two events"
            )
        seen[span] = promise.id
    observations.extend(_setup_coherence(draft, plan))
    return observations


def _setup_coherence(draft: PromiseLedgerDraft, plan: StoryPlan) -> list[str]:
    """Note payoffs whose event declares a structural setup the ledger did not open on.

    Advisory rather than enforced: payoff_of is optional in a valid plan, so requiring the
    ledger to mirror it would reject correct readings of plans that simply never used it.
    """
    by_id = {event.id: event for event in plan.events}
    findings = []
    for promise in draft.promises:
        event = by_id.get(promise.payoff.event_id)
        if event is None or not event.payoff_of:
            continue
        if promise.opening.event_id not in event.payoff_of:
            findings.append(
                f"promise {promise.id} pays off on {event.id}, whose declared setups are "
                f"{_join(event.payoff_of)}, but it opened on {promise.opening.event_id}"
            )
    return findings


def _join(values) -> str:
    """Render a set of identifiers the way every message in this module spells them."""
    return ", ".join(sorted(values))


def _event_positions(plan: StoryPlan) -> dict[str, int]:
    """Map every event ID to its place in the one order the plan is trusted to have."""
    if plan.topological_order:
        return {event_id: index for index, event_id in enumerate(plan.topological_order)}
    ordered: list[PlotEvent] = sorted(plan.events, key=attrgetter("order"))
    return {event.id: index for index, event in enumerate(ordered)}


def _anchored_events(draft: PromiseLedgerDraft) -> list[str]:
    """List every event ID the ledger anchors a beat to, in a stable order."""
    anchors: list[str] = []
    for promise in draft.promises:
        anchors.append(promise.opening.event_id)
        anchors.extend(progress.event_id for progress in promise.progress)
        anchors.append(promise.payoff.event_id)
    return sorted(set(anchors))


def _validate_size(draft: PromiseLedgerDraft, profile: NarrativeProfile) -> None:
    """Keep the promise count inside the band the profile leaves room to pay off."""
    low, high = promise_band(profile)
    count = len(draft.promises)
    if count < low:
        raise ValueError(f"{profile.value} profile requires at least {low} promises; got {count}")
    if count > high:
        raise ValueError(
            f"{profile.value} profile allows at most {high} promises because every promise "
            f"needs room for its own payoff; got {count}. Cut promises instead of leaving one "
            "unpaid."
        )


def _validate_identifiers(draft: PromiseLedgerDraft) -> None:
    """Require unique promise IDs and globally unique progress IDs."""
    promise_ids = [promise.id for promise in draft.promises]
    duplicates = {item for item in promise_ids if promise_ids.count(item) > 1}
    if duplicates:
        raise ValueError(f"promise IDs must be unique; repeated: {_join(duplicates)}")
    progress_ids = [progress.id for promise in draft.promises for progress in promise.progress]
    repeated = {item for item in progress_ids if progress_ids.count(item) > 1}
    if repeated:
        raise ValueError(f"progress IDs must be unique; repeated: {_join(repeated)}")


def _validate_primary(draft: PromiseLedgerDraft) -> None:
    """Require one primary promise, and require it to be the story-direction promise."""
    promises = {promise.id: promise for promise in draft.promises}
    primary = promises.get(draft.primary_promise_id)
    if primary is None:
        raise ValueError(
            f"primary_promise_id {draft.primary_promise_id} is not a promise of this ledger; "
            f"allowed values: {_join(promises)}"
        )
    if primary.kind != PRIMARY_KIND:
        raise ValueError(
            f"the primary promise must be the {PRIMARY_KIND} promise; {primary.id} is "
            f"{primary.kind}"
        )


def _validate_anchors(promise: PromiseContract, positions: dict[str, int]) -> None:
    """Require every beat of one promise to cite an event the plan already contains."""
    anchors = {
        "opening": [promise.opening.event_id],
        "progress": [progress.event_id for progress in promise.progress],
        "payoff": [promise.payoff.event_id],
    }
    for beat, event_ids in anchors.items():
        unknown = {item for item in event_ids if item not in positions}
        if unknown:
            raise ValueError(
                f"promise {promise.id} anchors its {beat} to unknown event IDs: "
                f"{_join(unknown)}; allowed event IDs: {_join(positions)}"
            )


def _validate_beat_order(promise: PromiseContract, positions: dict[str, int]) -> None:
    """Require the opening to precede every progress, and every progress to precede the payoff."""
    opening = positions[promise.opening.event_id]
    payoff = positions[promise.payoff.event_id]
    if payoff <= opening:
        raise ValueError(
            f"promise {promise.id} pays off on {promise.payoff.event_id}, which does not come "
            f"after its opening event {promise.opening.event_id}"
        )
    for progress in promise.progress:
        place = positions[progress.event_id]
        if not opening < place < payoff:
            raise ValueError(
                f"progress {progress.id} of promise {promise.id} anchors to "
                f"{progress.event_id}, which is not between the opening event "
                f"{promise.opening.event_id} and the payoff event {promise.payoff.event_id}"
            )


def _validate_preparation(promise: PromiseContract) -> None:
    """Require the payoff to be prepared only by progresses of its own promise."""
    owned = {progress.id for progress in promise.progress}
    foreign = set(promise.payoff.prepared_by_progress_ids) - owned
    if foreign:
        raise ValueError(
            f"promise {promise.id} claims preparation from {_join(foreign)}, which are not its "
            f"own progresses; allowed progress IDs: {_join(owned)}"
        )


def _validate_chapter_placement(
    promise: PromiseContract,
    chapter_by_event: dict[str, str],
    last_chapter: str,
    draft: PromiseLedgerDraft,
) -> None:
    """Keep openings out of the final chapter and land the primary payoff inside it."""
    if chapter_by_event[promise.opening.event_id] == last_chapter:
        raise ValueError(
            f"promise {promise.id} opens on {promise.opening.event_id}, in the final chapter "
            f"{last_chapter}; a promise opened there has no room left to be paid off"
        )
    if promise.id != draft.primary_promise_id:
        return
    landing = chapter_by_event[promise.payoff.event_id]
    if landing != last_chapter:
        raise ValueError(
            f"the primary promise {promise.id} must pay off in the final chapter "
            f"{last_chapter}; it pays off on {promise.payoff.event_id}, in {landing}"
        )
