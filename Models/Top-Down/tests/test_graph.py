import pytest

from asg_top_down.graph import chapter_word_budgets, materialize_plan, validate_story_plan
from asg_top_down.schemas import (
    ChapterDraft,
    ChapterPlan,
    CharacterProfile,
    CharactersArtifact,
    EventDependency,
    Location,
    PlotEvent,
    StoryPlan,
    StoryPlanDraft,
    StoryRequest,
    WorldArtifact,
)


def request(**changes) -> StoryRequest:
    values = {
        "original_prompt": "Una historia",
        "title": "Historia",
        "genre": "drama",
        "tone": "tense",
        "target_words": 600,
        "premise": "A choice has consequences",
    }
    values.update(changes)
    return StoryRequest(**values)


def world() -> WorldArtifact:
    return WorldArtifact(
        setting="A city",
        time_period="Present",
        rules=["Promises have consequences"],
        locations=[Location(id="square", name="Square", description="Central square")],
        atmosphere="Uneasy",
    )


def characters() -> CharactersArtifact:
    return CharactersArtifact(characters=[CharacterProfile(
        id="ana", name="Ana", role="protagonist", goal="Learn the truth",
        motivation="Protect her family", conflict="The truth is dangerous",
        arc="Chooses honesty", voice="Direct and observant",
    )])


def event(identifier: str, order: int, chapter: str = "chapter-1") -> PlotEvent:
    return PlotEvent(
        id=identifier,
        order=order,
        chapter_id=chapter,
        title=identifier,
        description=f"Event {identifier}",
        purpose="Advance the conflict",
        character_ids=["ana"],
        location_id="square",
        effects=["The situation changes"],
    )


def plan(dependencies: list[EventDependency]) -> StoryPlan:
    return StoryPlan(
        logline="Ana makes a choice",
        theme="Truth",
        ending="Ana accepts the cost",
        chapters=[ChapterPlan(
            id="chapter-1", order=1, title="Inicio", summary="The choice", target_words=600,
        )],
        events=[event("event-1", 1), event("event-2", 2), event("event-3", 3)],
        dependencies=dependencies,
    )


def dependency(source: str, target: str, relation: str = "causal") -> EventDependency:
    return EventDependency(
        source_event_id=source, target_event_id=target, relation=relation,
    )


def test_kahn_order_is_deterministic_for_a_branching_dag() -> None:
    candidate = plan([
        dependency("event-1", "event-3"),
        dependency("event-1", "event-2", "temporal"),
    ])
    assert validate_story_plan(candidate, world(), characters()) == [
        "event-1", "event-2", "event-3",
    ]


def test_cycle_is_rejected() -> None:
    candidate = plan([
        dependency("event-1", "event-2"),
        dependency("event-2", "event-1"),
    ])
    with pytest.raises(ValueError, match="cycle"):
        validate_story_plan(candidate, world(), characters())


def test_acyclic_backwards_dependency_is_rejected() -> None:
    candidate = plan([dependency("event-3", "event-1")])
    with pytest.raises(ValueError, match="backwards"):
        validate_story_plan(candidate, world(), characters())


def test_unknown_references_are_rejected() -> None:
    candidate = plan([])
    candidate.events[0].character_ids = ["unknown"]
    with pytest.raises(ValueError, match="unknown characters"):
        validate_story_plan(candidate, world(), characters())


def test_duplicate_event_ids_are_rejected() -> None:
    candidate = plan([])
    candidate.events[1].id = candidate.events[0].id
    with pytest.raises(ValueError, match="event ids"):
        validate_story_plan(candidate, world(), characters())


def test_every_chapter_requires_an_event() -> None:
    candidate = plan([])
    candidate.chapters.append(ChapterPlan(
        id="chapter-2", order=2, title="Fin", summary="Resolution", target_words=200,
    ))
    with pytest.raises(ValueError, match="without events"):
        validate_story_plan(candidate, world(), characters())


def test_global_event_order_must_follow_chapter_order() -> None:
    candidate = plan([])
    candidate.chapters.append(ChapterPlan(
        id="chapter-2", order=2, title="Fin", summary="Resolution", target_words=200,
    ))
    candidate.events[0].chapter_id = "chapter-2"
    candidate.events[1].chapter_id = "chapter-1"
    candidate.events[2].chapter_id = "chapter-2"
    with pytest.raises(ValueError, match="follow chapter order"):
        validate_story_plan(candidate, world(), characters())


def test_automatic_and_explicit_chapter_budgets() -> None:
    assert chapter_word_budgets(request(target_words=1800)) == [900, 900]
    assert chapter_word_budgets(request(target_words=601, requested_chapters=2)) == [301, 300]
    with pytest.raises(ValueError, match="200 words"):
        chapter_word_budgets(request(target_words=300, requested_chapters=2))


def test_materialize_plan_adds_budgets_and_trusted_order() -> None:
    draft = StoryPlanDraft(
        logline="Ana chooses",
        theme="Truth",
        ending="A cost is paid",
        chapters=[ChapterDraft(
            id="chapter-1", order=1, title="Inicio", summary="The choice",
        )],
        events=[event("event-1", 1)],
    )
    result = materialize_plan(draft, request(), world(), characters())
    assert result.chapters[0].target_words == 600
    assert result.topological_order == ["event-1"]
