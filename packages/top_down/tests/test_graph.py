import pytest
from asg_top_down.graph import (
    materialize_plan,
    validate_story_plan,
)
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
    WorldArtifact,
)


def world() -> WorldArtifact:
    return WorldArtifact(
        setting="A city",
        time_period="Present",
        rules=["Promises have consequences"],
        locations=[Location(id="square", name="Square", description="Central square")],
        atmosphere="Uneasy",
    )


def characters() -> CharactersArtifact:
    return CharactersArtifact(
        characters=[
            CharacterProfile(
                id="ana",
                name="Ana",
                role="protagonist",
                goal="Learn the truth",
                motivation="Protect her family",
                conflict="The truth is dangerous",
                arc="Chooses honesty",
                voice="Direct and observant",
            )
        ]
    )


def event(identifier: str, order: int, chapter: str = "chapter-1") -> PlotEvent:
    return PlotEvent(
        id=identifier,
        order=order,
        chapter_id=chapter,
        title=identifier,
        description=f"Event {identifier}",
        purpose="Advance the conflict",
        dramatic_function="Escalate the central choice",
        conflict="Ana must choose between safety and truth",
        outcome="Ana gains knowledge and accepts a cost",
        character_ids=["ana"],
        location_id="square",
        effects=["The situation changes"],
    )


def plan(dependencies: list[EventDependency]) -> StoryPlan:
    return StoryPlan(
        logline="Ana makes a choice",
        theme="Truth",
        ending="Ana accepts the cost",
        narrative_structure="Three-act structure",
        dramatic_question="Will Ana reveal the truth?",
        stakes="Her family and community are at risk",
        chapters=[
            ChapterPlan(
                id="chapter-1",
                order=1,
                title="The Beginning",
                summary="The choice",
                dramatic_goal="Force Ana to confront the hidden truth",
                opening_state="Ana trusts the official account",
                turning_point="She finds contradictory evidence",
                closing_state="Ana decides to investigate",
            )
        ],
        events=[event("event-1", 1), event("event-2", 2), event("event-3", 3)],
        dependencies=dependencies,
    )


def dependency(source: str, target: str, relation: str = "causal") -> EventDependency:
    return EventDependency(
        source_event_id=source,
        target_event_id=target,
        relation=relation,
    )


def test_kahn_order_is_deterministic_for_a_branching_dag() -> None:
    candidate = plan(
        [
            dependency("event-1", "event-3"),
            dependency("event-1", "event-2", "temporal"),
        ]
    )
    assert validate_story_plan(candidate, world(), characters()) == [
        "event-1",
        "event-2",
        "event-3",
    ]


def test_cycle_is_rejected() -> None:
    candidate = plan(
        [
            dependency("event-1", "event-2"),
            dependency("event-2", "event-1"),
            dependency("event-2", "event-3"),
        ]
    )
    with pytest.raises(ValueError, match="cycle"):
        validate_story_plan(candidate, world(), characters())


def test_acyclic_backwards_dependency_is_rejected() -> None:
    candidate = plan([dependency("event-3", "event-1"), dependency("event-1", "event-2")])
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
    candidate.chapters.append(
        ChapterPlan(
            id="chapter-2",
            order=2,
            title="The End",
            summary="Resolution",
            dramatic_goal="Resolve the truth",
            opening_state="Ana faces opposition",
            turning_point="The evidence becomes public",
            closing_state="The town accepts the cost",
        )
    )
    with pytest.raises(ValueError, match="chapters without events"):
        validate_story_plan(candidate, world(), characters())


def test_global_event_order_must_follow_chapter_order() -> None:
    candidate = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    candidate.chapters.append(
        ChapterPlan(
            id="chapter-2",
            order=2,
            title="The End",
            summary="Resolution",
            dramatic_goal="Resolve the truth",
            opening_state="Ana faces opposition",
            turning_point="The evidence becomes public",
            closing_state="The town accepts the cost",
        )
    )
    candidate.events.append(event("event-4", 4, "chapter-2"))
    candidate.dependencies.append(dependency("event-3", "event-4"))
    candidate.events[0].chapter_id = "chapter-2"
    candidate.events[3].chapter_id = "chapter-1"
    with pytest.raises(ValueError, match="follow chapter order"):
        validate_story_plan(candidate, world(), characters())


def test_materialize_plan_accepts_qualitative_size_and_adds_trusted_order() -> None:
    draft = StoryPlanDraft(
        logline="Ana chooses",
        theme="Truth",
        ending="A cost is paid",
        narrative_structure="Three-act structure",
        dramatic_question="Will Ana tell the truth?",
        stakes="Her family may reject her",
        chapters=[
            ChapterDraft(
                id="chapter-1",
                order=1,
                title="The Choice",
                summary="The choice",
                dramatic_goal="Make the choice unavoidable",
                opening_state="Ana is uncertain",
                turning_point="She finds proof",
                closing_state="Ana commits to the truth",
            )
        ],
        events=[event("event-1", 1), event("event-2", 2)],
        dependencies=[dependency("event-1", "event-2")],
    )
    result = materialize_plan(draft, world(), characters())
    assert len(result.chapters) == 1
    assert result.topological_order == ["event-1", "event-2"]


def test_same_profile_accepts_different_valid_graph_sizes() -> None:
    compact = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    validate_story_plan(compact, world(), characters())
    expanded = compact.model_copy(deep=True)
    expanded.events.append(event("event-4", 4))
    expanded.dependencies.append(dependency("event-3", "event-4"))
    assert validate_story_plan(expanded, world(), characters()) == [
        "event-1",
        "event-2",
        "event-3",
        "event-4",
    ]


def test_disconnected_or_noncausal_graph_is_rejected() -> None:
    with pytest.raises(ValueError, match="causal"):
        validate_story_plan(
            plan(
                [
                    dependency("event-1", "event-2", "temporal"),
                    dependency("event-2", "event-3", "temporal"),
                ]
            ),
            world(),
            characters(),
        )
    with pytest.raises(ValueError, match="weakly connected"):
        validate_story_plan(
            plan([dependency("event-1", "event-2")]),
            world(),
            characters(),
        )


def test_unknown_payoff_reports_value_and_allowed_earlier_events() -> None:
    candidate = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    candidate.events[1].payoff_of = ["charcoal_note"]
    with pytest.raises(ValueError) as captured:
        validate_story_plan(candidate, world(), characters())
    message = str(captured.value)
    assert "unknown event IDs: charcoal_note" in message
    assert "allowed earlier event IDs: event-1" in message


def test_future_payoff_reports_only_earlier_events_as_allowed() -> None:
    candidate = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    candidate.events[1].payoff_of = ["event-3"]
    with pytest.raises(ValueError) as captured:
        validate_story_plan(candidate, world(), characters())
    message = str(captured.value)
    assert "non-earlier event IDs: event-3" in message
    assert "allowed earlier event IDs: event-1" in message


def test_valid_or_empty_payoff_references_are_accepted() -> None:
    candidate = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    candidate.events[2].payoff_of = ["event-1"]
    assert validate_story_plan(candidate, world(), characters()) == [
        "event-1",
        "event-2",
        "event-3",
    ]
    candidate.events[2].payoff_of = []
    assert validate_story_plan(candidate, world(), characters()) == [
        "event-1",
        "event-2",
        "event-3",
    ]


def test_payoff_schema_distinguishes_event_ids_from_story_state() -> None:
    properties = PlotEvent.model_json_schema()["properties"]
    assert "earlier event" in properties["payoff_of"]["description"]
    assert "not IDs" in properties["effects"]["description"]
