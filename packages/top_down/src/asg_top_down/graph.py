"""Deterministic validation and ordering for the Top-Down event DAG."""

from __future__ import annotations

import math
from operator import attrgetter

from .schemas import (
    ChapterPlan,
    CharactersArtifact,
    PlotEvent,
    StoryPlan,
    StoryPlanDraft,
    StoryRequest,
    WorldArtifact,
)


def chapter_word_budgets(request: StoryRequest) -> list[int]:
    """Calculate exact chapter budgets without delegating arithmetic to an LLM."""
    if request.requested_chapters:
        count = request.requested_chapters
        if request.target_words < count * 200:
            raise ValueError("explicit chapter count requires at least 200 words per chapter")
    else:
        count = max(1, math.ceil(request.target_words / 900))
    base, remainder = divmod(request.target_words, count)
    return [base + (1 if index < remainder else 0) for index in range(count)]


def chapter_event_budgets(request: StoryRequest) -> list[int]:
    """Derive an exact, length-aware event count for every chapter."""
    return [max(1, math.ceil(words / 450)) for words in chapter_word_budgets(request)]


def materialize_plan(
    draft: StoryPlanDraft,
    request: StoryRequest,
    world: WorldArtifact,
    characters: CharactersArtifact,
) -> StoryPlan:
    """Add local word budgets, validate the graph, and compute its only trusted order."""
    budgets = chapter_word_budgets(request)
    chapters = sorted(draft.chapters, key=attrgetter("order"))
    if len(chapters) != len(budgets):
        raise ValueError(f"plan must contain exactly {len(budgets)} chapters")
    plan = StoryPlan(
        logline=draft.logline,
        theme=draft.theme,
        ending=draft.ending,
        narrative_structure=draft.narrative_structure,
        dramatic_question=draft.dramatic_question,
        stakes=draft.stakes,
        chapters=[
            ChapterPlan(**chapter.model_dump(), target_words=budget)
            for chapter, budget in zip(chapters, budgets, strict=True)
        ],
        events=draft.events,
        dependencies=draft.dependencies,
    )
    _validate_event_budgets(plan)
    plan.topological_order = validate_story_plan(plan, world, characters)
    return plan


def validate_story_plan(
    plan: StoryPlan,
    world: WorldArtifact,
    characters: CharactersArtifact,
) -> list[str]:
    """Validate only objective structural invariants and return a stable Kahn order."""
    chapter_order_by_id = _validate_chapters(plan)
    _validate_event_budgets(plan)
    event_ids, order_by_id = _validate_events(plan, world, characters, chapter_order_by_id)
    incoming, outgoing = _dependency_graph(plan, event_ids)
    _validate_dependency_shape(plan, event_ids, outgoing)
    result = _stable_topological_order(event_ids, order_by_id, incoming, outgoing)
    _validate_dependency_directions(plan, order_by_id)
    return result


def relevant_prior_events(
    plan: StoryPlan,
    current_event_ids: set[str],
) -> list[PlotEvent]:
    """Return topologically ordered ancestors that can affect the current events."""
    reverse = {event.id: set() for event in plan.events}
    for dependency in plan.dependencies:
        reverse[dependency.target_event_id].add(dependency.source_event_id)
    ancestors: set[str] = set()
    pending = list(current_event_ids)
    while pending:
        current = pending.pop()
        for source in reverse.get(current, set()):
            if source not in ancestors and source not in current_event_ids:
                ancestors.add(source)
                pending.append(source)
    by_id = {event.id: event for event in plan.events}
    return [by_id[event_id] for event_id in plan.topological_order if event_id in ancestors]


def _validate_event_budgets(plan: StoryPlan) -> None:
    """Require the deterministic number of events implied by each chapter budget."""
    counts = {chapter.id: 0 for chapter in plan.chapters}
    for event in plan.events:
        if event.chapter_id in counts:
            counts[event.chapter_id] += 1
    expected = {
        chapter.id: max(1, math.ceil(chapter.target_words / 450)) for chapter in plan.chapters
    }
    mismatches = [
        f"{chapter_id}: expected {expected[chapter_id]}, received {counts[chapter_id]}"
        for chapter_id in expected
        if counts[chapter_id] != expected[chapter_id]
    ]
    if mismatches:
        raise ValueError("invalid chapter event budgets: " + "; ".join(mismatches))


def _validate_chapters(plan: StoryPlan) -> dict[str, int]:
    """Validate chapter identifiers and return their configured order."""
    chapter_ids = [item.id for item in plan.chapters]
    chapter_orders = [item.order for item in plan.chapters]
    if len(chapter_ids) != len(set(chapter_ids)):
        raise ValueError("chapter ids must be unique")
    if chapter_orders != list(range(1, len(plan.chapters) + 1)):
        raise ValueError("chapter orders must be consecutive")

    return {item.id: item.order for item in plan.chapters}


def _validate_events(
    plan: StoryPlan,
    world: WorldArtifact,
    characters: CharactersArtifact,
    chapter_order_by_id: dict[str, int],
) -> tuple[list[str], dict[str, int]]:
    """Validate event identity, ordering, chapters, and entity references."""
    event_ids = [item.id for item in plan.events]
    event_orders = [item.order for item in plan.events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("event ids must be unique")
    if sorted(event_orders) != list(range(1, len(plan.events) + 1)):
        raise ValueError("event orders must be unique and consecutive")

    known_chapters = set(chapter_order_by_id)
    known_characters = {item.id for item in characters.characters}
    known_locations = {item.id for item in world.locations}
    known_objects = {item.id for item in world.objects}
    order_by_id = {item.id: item.order for item in plan.events}
    events_by_chapter = dict.fromkeys(chapter_order_by_id, 0)
    for event in plan.events:
        if event.chapter_id not in known_chapters:
            raise ValueError(f"event {event.id} references an unknown chapter")
        events_by_chapter[event.chapter_id] += 1
        if set(event.character_ids) - known_characters:
            raise ValueError(f"event {event.id} references unknown characters")
        if event.location_id and event.location_id not in known_locations:
            raise ValueError(f"event {event.id} references an unknown location")
        if set(event.object_ids) - known_objects:
            raise ValueError(f"event {event.id} references unknown objects")
        allowed_payoffs = [
            candidate.id for candidate in plan.events if candidate.order < event.order
        ]
        unknown_payoffs = sorted(set(event.payoff_of) - set(event_ids))
        if unknown_payoffs:
            raise ValueError(
                f"event {event.id} payoff_of contains unknown event IDs: "
                f"{', '.join(unknown_payoffs)}; allowed earlier event IDs: "
                f"{', '.join(allowed_payoffs) if allowed_payoffs else '(none)'}"
            )
        future_payoffs = sorted(
            source for source in event.payoff_of if order_by_id[source] >= event.order
        )
        if future_payoffs:
            raise ValueError(
                f"event {event.id} payoff_of contains non-earlier event IDs: "
                f"{', '.join(future_payoffs)}; allowed earlier event IDs: "
                f"{', '.join(allowed_payoffs) if allowed_payoffs else '(none)'}"
            )
    empty = [identifier for identifier, count in events_by_chapter.items() if not count]
    if empty:
        raise ValueError(f"chapters without events: {', '.join(empty)}")
    ordered_events = sorted(plan.events, key=attrgetter("order"))
    chapter_sequence = [chapter_order_by_id[item.chapter_id] for item in ordered_events]
    if chapter_sequence != sorted(chapter_sequence):
        raise ValueError("event order must follow chapter order")
    return event_ids, {item.id: item.order for item in plan.events}


def _dependency_graph(
    plan: StoryPlan, event_ids: list[str]
) -> tuple[dict[str, int], dict[str, list[str]]]:
    """Validate dependency endpoints and build incoming and outgoing indexes."""
    known_events = set(event_ids)
    incoming = dict.fromkeys(event_ids, 0)
    outgoing = {identifier: [] for identifier in event_ids}
    seen_edges: set[tuple[str, str]] = set()
    for dependency in plan.dependencies:
        source = dependency.source_event_id
        target = dependency.target_event_id
        if {source, target} - known_events:
            raise ValueError("dependencies reference unknown events")
        if source == target:
            raise ValueError("event dependencies cannot be self-referential")
        signature = (source, target)
        if signature in seen_edges:
            raise ValueError("event dependencies must be unique")
        seen_edges.add(signature)
        incoming[target] += 1
        outgoing[source].append(target)
    return incoming, outgoing


def _validate_dependency_shape(
    plan: StoryPlan,
    event_ids: list[str],
    outgoing: dict[str, list[str]],
) -> None:
    """Require a connected event graph with an explicit causal backbone."""
    if len(event_ids) <= 1:
        return
    if not any(item.relation == "causal" for item in plan.dependencies):
        raise ValueError("a multi-event plan requires at least one causal dependency")

    neighbors = {identifier: set() for identifier in event_ids}
    for source, targets in outgoing.items():
        for target in targets:
            neighbors[source].add(target)
            neighbors[target].add(source)
    visited: set[str] = set()
    pending = [event_ids[0]]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(neighbors[current] - visited)
    if visited != set(event_ids):
        raise ValueError("event dependency graph must be weakly connected")


def _stable_topological_order(
    event_ids: list[str],
    order_by_id: dict[str, int],
    incoming: dict[str, int],
    outgoing: dict[str, list[str]],
) -> list[str]:
    """Return a deterministic Kahn order or reject a dependency cycle."""
    ready = sorted(
        (identifier for identifier, count in incoming.items() if count == 0),
        key=order_by_id.get,
    )
    result: list[str] = []
    while ready:
        identifier = ready.pop(0)
        result.append(identifier)
        for target in sorted(outgoing[identifier], key=order_by_id.get):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort(key=order_by_id.get)
    if len(result) != len(event_ids):
        raise ValueError("event dependencies contain a cycle")
    return result


def _validate_dependency_directions(plan: StoryPlan, order_by_id: dict[str, int]) -> None:
    """Require every dependency to point forward in narrative event order."""
    for dependency in plan.dependencies:
        source = dependency.source_event_id
        target = dependency.target_event_id
        if order_by_id[source] >= order_by_id[target]:
            raise ValueError(f"dependency {source}->{target} points backwards")
