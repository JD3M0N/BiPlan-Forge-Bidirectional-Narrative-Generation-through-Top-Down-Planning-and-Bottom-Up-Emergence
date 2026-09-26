"""Repair blocks reinjected verbatim into the planner prompt after a rejected plan.

Every string built here travels to the model, so it stays in English for the same reason
graph.py's ValueError messages do: it is part of the contract with the model, not text for
a reader. The entry point is ``repair_guidance``, which picks the block matching one
validation failure class; the rest describe the rejected candidate back to the planner in
the terms of the rule it broke.
"""

from __future__ import annotations

import json
from collections import Counter

from ..schemas import PlotEvent, StoryPlanDraft
from .profiles import MIN_EVENTS_PER_CHAPTER, NarrativeProfile, profile_event_target


def repair_guidance(draft: StoryPlanDraft, issue: str, profile: NarrativeProfile) -> str:
    """Return the repair block that matches one validation failure class."""
    if "causal dependency branch" in issue:
        return _causal_branch_repair_rules(draft)
    if ("requires at least" in issue and "events" in issue) or ("chapters without events" in issue):
        return _event_budget_repair_rules(draft, profile)
    if "points backwards" in issue:
        return _dependency_direction_repair_rules(draft, issue)
    if "payoff_of" in issue:
        return (
            "For payoff_of, use only an exact event_id listed in allowed_earlier_event_ids "
            "for that event. Never copy object IDs, character IDs, location IDs, names, or "
            "prose into payoff_of; use [] when there is no valid earlier setup.\n"
            f"PAYOFF_OF REFERENCE MATRIX:\n{_payoff_reference_rules(draft)}\n"
        )
    return ""


def _event_budget_repair_rules(draft: StoryPlanDraft, profile: NarrativeProfile) -> str:
    """Say how many events are missing and which chapters are too thin to carry a scene."""
    low_events, high_events = profile_event_target(profile)
    counts = Counter(event.chapter_id for event in draft.events)
    ordered = sorted(draft.chapters, key=lambda chapter: chapter.order)
    table = [
        {"chapter_id": chapter.id, "order": chapter.order, "events": counts.get(chapter.id, 0)}
        for chapter in ordered
    ]
    thin = [chapter.id for chapter in ordered if counts.get(chapter.id, 0) < MIN_EVENTS_PER_CHAPTER]
    missing = max(low_events - len(draft.events), 0)
    lines = [
        f"This profile needs {low_events} to {high_events} events across "
        f"{len(ordered)} chapters, because every chapter must carry at least "
        f"{MIN_EVENTS_PER_CHAPTER} events. You planned {len(draft.events)}.",
        f"CURRENT EVENTS PER CHAPTER:\n{json.dumps(table, ensure_ascii=False, indent=2)}",
    ]
    if missing:
        lines.append(
            f"ADD at least {missing} more causally meaningful events to reach {low_events}."
        )
    if thin:
        lines.append(
            "These chapters carry fewer than the required events and need new material: "
            f"{', '.join(thin)}."
        )
    lines.append(
        "Every added event must change conflict, knowledge, relationships, resources, stakes "
        "or consequences. Do not split one unchanged action into smaller events, and do not "
        "drop chapters to meet the count."
    )
    return "\n".join(lines) + "\n"


def _causal_degrees(
    draft: StoryPlanDraft,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Index the causal out- and in-neighbours of every event in one candidate."""
    outgoing: dict[str, list[str]] = {event.id: [] for event in draft.events}
    incoming: dict[str, list[str]] = {event.id: [] for event in draft.events}
    for dependency in draft.dependencies:
        if dependency.relation != "causal":
            continue
        source = dependency.source_event_id
        target = dependency.target_event_id
        if source in outgoing and target in incoming:
            outgoing[source].append(target)
            incoming[target].append(source)
    return outgoing, incoming


def _causal_branch_repair_rules(draft: StoryPlanDraft) -> str:
    """Spell out the forward edge that turns one candidate into a branch and a join."""
    ordered = sorted(draft.events, key=lambda event: event.order)
    outgoing, incoming = _causal_degrees(draft)
    table = [
        {
            "event_id": event.id,
            "order": event.order,
            "outgoing_causal": outgoing[event.id],
            "incoming_causal": incoming[event.id],
        }
        for event in ordered
    ]
    blocks = [
        "THIS IS A DIRECTION PROBLEM, NOT A COUNTING PROBLEM. One event must have two "
        "outgoing causal dependencies (the branch) and a LATER event must have two incoming "
        "causal dependencies (the join), so branch.order < join.order. Every dependency must "
        "satisfy source.order < target.order. Two independent early events that converge are "
        "parallel roots, not a branch.",
        f"CURRENT CAUSAL DEGREES:\n{json.dumps(table, ensure_ascii=False, indent=2)}",
    ]
    repair = _suggested_branch_edge(ordered, outgoing, incoming)
    if repair:
        blocks.append(repair)
    return "\n".join(blocks) + "\n"


def _suggested_branch_edge(
    ordered: list[PlotEvent],
    outgoing: dict[str, list[str]],
    incoming: dict[str, list[str]],
) -> str:
    """Name one concrete forward edge that satisfies the branch-and-join contract."""
    joins = [event for event in ordered if len(incoming[event.id]) >= 2]
    for join in joins:
        for source in ordered:
            if source.order >= join.order or len(outgoing[source.id]) != 1:
                continue
            targets = [
                candidate
                for candidate in ordered
                if candidate.order > source.order
                and candidate.id not in outgoing[source.id]
                and candidate.id != join.id
            ]
            if not targets:
                continue
            target = targets[0]
            return (
                f"ADD this causal dependency: {source.id} -> {target.id}. It gives "
                f"{source.id} (order {source.order}) two outgoing causal dependencies, so it "
                f"becomes the branch, while {join.id} (order {join.order}) keeps the two "
                f"incoming ones that already make it the join. The edge points forward "
                f"({source.order} < {target.order}) and the branch precedes the join "
                f"({source.order} < {join.order}). Keep every other dependency unchanged."
            )
    if len(ordered) >= 4:
        branch, first, second, join = ordered[0], ordered[1], ordered[2], ordered[3]
        return (
            f"BUILD the branch and the join like this: {branch.id} -> {first.id} and "
            f"{branch.id} -> {second.id} make {branch.id} the branch; {first.id} -> "
            f"{join.id} and {second.id} -> {join.id} make {join.id} the join. Every one of "
            "those edges points forward and the branch precedes the join."
        )
    return ""


def _dependency_direction_repair_rules(draft: StoryPlanDraft, issue: str) -> str:
    """Explain the offending backwards edge in terms of the two event orders."""
    order_by_id = {event.id: event.order for event in draft.events}
    offending = ""
    for dependency in draft.dependencies:
        source = dependency.source_event_id
        target = dependency.target_event_id
        if f"{source}->{target}" not in issue:
            continue
        if source not in order_by_id or target not in order_by_id:
            continue
        offending = (
            f"The rejected edge {source} -> {target} runs from order "
            f"{order_by_id[source]} back to order {order_by_id[target]}. Either reverse it to "
            f"{target} -> {source}, or re-target it to an event whose order is greater than "
            f"{order_by_id[source]}. "
        )
        break
    return (
        f"{offending}Every dependency must satisfy source.order < target.order. Do not "
        "renumber the events to make a backwards edge legal: add the missing causal structure "
        "with forward edges instead.\n"
    )


def _payoff_reference_rules(draft: StoryPlanDraft) -> str:
    """Describe the exact payoff references allowed by one rejected candidate."""
    ordered = sorted(draft.events, key=lambda event: event.order)
    rules = [
        {
            "event_id": event.id,
            "current_payoff_of": event.payoff_of,
            "allowed_earlier_event_ids": [
                candidate.id for candidate in ordered if candidate.order < event.order
            ],
        }
        for event in ordered
    ]
    return json.dumps(rules, ensure_ascii=False, indent=2)
