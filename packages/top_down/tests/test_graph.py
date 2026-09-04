import pytest
from asg_top_down.graph import (
    materialize_plan,
    validate_profile_structure,
    validate_story_plan,
)
from asg_top_down.profiles import NarrativeProfile
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


def profile_plan(event_count: int) -> StoryPlan:
    """Build a valid linear plan with the requested number of events."""
    candidate = plan(
        [dependency("event-1", "event-2"), dependency("event-2", "event-3")]
    )
    for order in range(4, event_count + 1):
        identifier = f"event-{order}"
        candidate.events.append(event(identifier, order))
        candidate.dependencies.append(dependency(f"event-{order - 1}", identifier))
    validate_story_plan(candidate, world(), characters())
    return candidate


def test_essential_profile_keeps_compact_plan_valid() -> None:
    validate_profile_structure(profile_plan(3), NarrativeProfile.ESSENTIAL)


@pytest.mark.parametrize(
    ("profile", "minimum", "actual"),
    [
        (NarrativeProfile.DEVELOPED, 6, 5),
        (NarrativeProfile.EXPANSIVE, 9, 8),
    ],
)
def test_larger_profiles_reject_too_few_events(profile, minimum, actual) -> None:
    with pytest.raises(
        ValueError,
        match=rf"{profile.value} profile requires at least {minimum} events; got {actual}",
    ):
        validate_profile_structure(profile_plan(actual), profile)


def test_developed_profile_accepts_six_meaningful_events() -> None:
    validate_profile_structure(profile_plan(6), NarrativeProfile.DEVELOPED)


def test_expansive_profile_requires_a_causal_branch_and_later_join() -> None:
    with pytest.raises(ValueError, match="causal dependency branch"):
        validate_profile_structure(profile_plan(9), NarrativeProfile.EXPANSIVE)


def test_expansive_profile_accepts_a_causal_branch_and_later_join() -> None:
    candidate = profile_plan(9)
    candidate.dependencies = [
        dependency("event-1", "event-2"),
        dependency("event-1", "event-3"),
        dependency("event-2", "event-4"),
        dependency("event-3", "event-4"),
        dependency("event-4", "event-5"),
        dependency("event-5", "event-6"),
        dependency("event-6", "event-7"),
        dependency("event-7", "event-8"),
        dependency("event-8", "event-9"),
    ]
    validate_story_plan(candidate, world(), characters())
    validate_profile_structure(candidate, NarrativeProfile.EXPANSIVE)


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


def test_structural_error_messages_stay_in_english() -> None:
    """Validation messages feed the model's repair prompt, so they must stay ASCII English."""
    messages: list[str] = []

    def collect(candidate: StoryPlan) -> None:
        with pytest.raises(ValueError) as captured:
            validate_story_plan(candidate, world(), characters())
        messages.append(str(captured.value))

    duplicate_chapter = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    duplicate_chapter.chapters.append(duplicate_chapter.chapters[0])
    collect(duplicate_chapter)

    unknown_chapter = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    unknown_chapter.events[0].chapter_id = "missing-chapter"
    collect(unknown_chapter)

    disconnected = plan(
        [dependency("event-1", "event-2", "temporal"), dependency("event-2", "event-3", "temporal")]
    )
    collect(disconnected)

    unknown_payoff = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    unknown_payoff.events[1].payoff_of = ["charcoal_note"]
    collect(unknown_payoff)

    assert messages
    for message in messages:
        assert message.isascii(), message
