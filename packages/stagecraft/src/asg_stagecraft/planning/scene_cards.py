"""Validate the scene cards drawn over a frozen plan, like graph.py validates the plan (7.17).

The scene_cards arm. In 7.10 the Drafter went from one English event to about 350 words of
Spanish prose in a single step and filled the gap with weather and summary: 12 of 14 chapters
opened on the air, and resolutions came as "Semanas despues...". DOC, Re3 and StoryWriter all
put a finer outline between plan and prose, and more concrete content in the prompt measurably
raises the prose (AI-Slop to AI-Polish, COLM 2025). A card is that outline for one scene.

The cards change how the plan is written, never what it contains: every card names an event of
the frozen plan, and no event goes without one. The ValueError messages stay in English ASCII
because they are reinjected into the repair prompt, exactly like graph.py's.
"""

from __future__ import annotations

from ..schemas import CharactersArtifact, SceneCard, SceneCardsDraft, StoryPlan, WorldArtifact

# Two scenes give an event its action and its reaction; a third starts to stretch it.
MAX_CARDS_PER_EVENT = 2


def materialize_cards(
    draft: SceneCardsDraft,
    plan: StoryPlan,
    world: WorldArtifact,
    characters: CharactersArtifact,
) -> list[SceneCard]:
    """Return the cards in plan order, normalized, or raise saying in English what to fix.

    An unknown location is dropped and an unknown character left out, since each has one
    correct reading; a card for an event the plan lacks, an event with no card and an event
    with too many are rejected.
    """
    events = set(plan.topological_order)
    locations = {location.id for location in world.locations}
    known = {character.id for character in characters.characters}
    by_event: dict[str, list[SceneCard]] = {}
    for card in draft.cards:
        if card.event_id not in events:
            raise ValueError(f"a scene card names an event the plan does not have: {card.event_id}")
        cast = [item for item in dict.fromkeys(card.character_ids) if item in known]
        if not cast:
            raise ValueError(f"the scene card of {card.event_id} names no known character id")
        location = card.location_id if card.location_id in locations else ""
        by_event.setdefault(card.event_id, []).append(
            card.model_copy(update={"character_ids": cast, "location_id": location})
        )
    missing = [event_id for event_id in plan.topological_order if event_id not in by_event]
    if missing:
        raise ValueError(f"every event needs a scene card; none for: {', '.join(missing)}")
    crowded = [event_id for event_id, cards in by_event.items() if len(cards) > MAX_CARDS_PER_EVENT]
    if crowded:
        raise ValueError(
            "give each event one scene card, or two when it needs an action and a reaction; "
            f"too many for: {', '.join(crowded)}"
        )
    return [card for event_id in plan.topological_order for card in by_event[event_id]]


def chapter_cards(cards: list[SceneCard], plan: StoryPlan, chapter_id: str) -> list[SceneCard]:
    """Return the cards of one chapter's events, in plan order."""
    chapter_of = {event.id: event.chapter_id for event in plan.events}
    return [card for card in cards if chapter_of.get(card.event_id) == chapter_id]
