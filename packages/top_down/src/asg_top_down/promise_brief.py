"""Prompt blocks rendered from a validated promise ledger.

Pure and deterministic, like craft_evidence: the ledger is data, these are the exact texts that
reach the Drafter, the Writer and the Drama Critic. No count and no profile figure is ever
rendered here. What travels is an obligation attached to an event the agent is already working
on, which is the only form in which promise craft can turn into prose instead of theory.
"""

from __future__ import annotations

from operator import attrgetter

from .schemas import ChapterPlan, PlotEvent, PromiseContract, PromiseLedger, StoryPlan

CHAPTER_PREFACE = (
    "Honor these while you dramatize the events below. Render every obligation inside its event, "
    "through what happens and what is said; never announce it, never name a promise, and never "
    "let the reader see the bookkeeping."
)

CRITIC_PREFACE = (
    "The story opened these expectations and owes each one a visible answer. Return one entry in "
    "promise_checks for every promise listed, quoting the draft as evidence. Promise IDs belong "
    "in promise_checks only: event_ids and chapter_ids of a revision note must contain plan IDs."
)


def event_index(plan: StoryPlan) -> str:
    """Render the exact set of events a ledger beat may anchor to."""
    by_id = {event.id: event for event in plan.events}
    ordered = [by_id[event_id] for event_id in plan.topological_order] or sorted(
        plan.events, key=attrgetter("order")
    )
    lines = [
        f"- {event.id} | chapter {event.chapter_id} | {event.title}: {event.purpose}"
        for event in ordered
    ]
    return "\n".join(lines)


def chapter_brief(
    ledger: PromiseLedger | None,
    chapter: ChapterPlan,
    events: list[PlotEvent],
) -> str:
    """Render what one chapter owes the reader, event by event, or nothing when it owes none."""
    if ledger is None:
        return ""
    lines: list[str] = []
    for event in events:
        lines.extend(_event_obligations(ledger, event))
    if not lines:
        return ""
    return "\n".join([CHAPTER_PREFACE, *lines])


def critic_obligations(ledger: PromiseLedger | None) -> str:
    """Render the checklist the Drama Critic verifies one promise at a time."""
    if ledger is None:
        return ""
    lines = [CRITIC_PREFACE]
    for promise in _ordered_promises(ledger):
        mark = " (primary)" if promise.id == ledger.primary_promise_id else ""
        opening = _placed(ledger, promise.opening.event_id)
        payoff = _placed(ledger, promise.payoff.event_id)
        progress = ", ".join(_placed(ledger, item.event_id) for item in promise.progress)
        lines.append(
            f"- {promise.id}{mark} | {promise.dramatic_question}\n"
            f"  opened at {opening} as: {promise.opening.signal}\n"
            f"  progressed at {progress}\n"
            f"  paid at {payoff} as: {promise.payoff.answer} (cost: {promise.payoff.cost})"
        )
    return "\n".join(lines)


def rendered_ledger(ledger: PromiseLedger, plan: StoryPlan) -> PromiseLedger:
    """Return the ledger carrying the exact blocks that will travel to the model.

    Storing them on the artifact is what CraftEvidenceArtifact does with its own block: it keeps
    a finished run auditable without having to re-derive what the agents were told.
    """
    by_id = {event.id: event for event in plan.events}
    ordered = plan.topological_order or [
        event.id for event in sorted(plan.events, key=attrgetter("order"))
    ]
    blocks = {}
    for chapter in plan.chapters:
        events = [
            by_id[event_id] for event_id in ordered if by_id[event_id].chapter_id == chapter.id
        ]
        block = chapter_brief(ledger, chapter, events)
        if block:
            blocks[chapter.id] = block
    return ledger.model_copy(
        update={"chapter_blocks": blocks, "critic_block": critic_obligations(ledger)}
    )


def _ordered_promises(ledger: PromiseLedger) -> list[PromiseContract]:
    """List the promises with the primary one first, so importance survives the rendering."""
    primary = [item for item in ledger.promises if item.id == ledger.primary_promise_id]
    rest = [item for item in ledger.promises if item.id != ledger.primary_promise_id]
    return primary + rest


def _placed(ledger: PromiseLedger, event_id: str) -> str:
    """Name one anchor event together with the chapter the plan puts it in."""
    chapter = ledger.chapter_by_event.get(event_id)
    return f"{event_id} ({chapter})" if chapter else event_id


def _event_obligations(ledger: PromiseLedger, event: PlotEvent) -> list[str]:
    """List every ledger obligation that lands on one event, openings first."""
    lines: list[str] = []
    for promise in _ordered_promises(ledger):
        if promise.opening.event_id == event.id:
            lines.append(
                f"- {event.id} | OPEN {promise.id}: {promise.opening.signal} The reader must "
                f"leave this beat expecting {promise.opening.reader_expectation}"
            )
        for progress in promise.progress:
            if progress.event_id != event.id:
                continue
            lines.append(
                f"- {event.id} | PROGRESS {promise.id} ({promise.dramatic_question}): "
                f"{progress.observable_delta} What this changes: "
                f"{progress.new_cost_or_information}"
            )
        if promise.payoff.event_id == event.id:
            lines.append(
                f"- {event.id} | PAY OFF {promise.id} ({promise.dramatic_question}): "
                f"{promise.payoff.answer} It costs: {promise.payoff.cost} Play it so it lands as "
                f"earned rather than announced: {promise.payoff.surprising_without_breach}"
            )
    return lines
