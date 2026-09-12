import pytest
from asg_top_down.graph import (
    materialize_plan,
    validate_profile_structure,
    validate_story_plan,
)
from asg_top_down.profiles import (
    MIN_EVENTS_PER_CHAPTER,
    NarrativeProfile,
    profile_chapter_band,
    profile_event_aim,
    profile_event_floor,
    profile_event_target,
    profile_min_events,
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


def second_chapter(order: int = 2) -> ChapterPlan:
    return ChapterPlan(
        id="chapter-2",
        order=order,
        title="The End",
        summary="Resolution",
        dramatic_goal="Resolve the truth",
        opening_state="Ana faces opposition",
        turning_point="The evidence becomes public",
        closing_state="The town accepts the cost",
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


def _cycle(candidate: StoryPlan) -> None:
    candidate.dependencies = [
        dependency("event-1", "event-2"),
        dependency("event-2", "event-1"),
        dependency("event-2", "event-3"),
    ]


def _backwards_dependency(candidate: StoryPlan) -> None:
    candidate.dependencies = [dependency("event-3", "event-1"), dependency("event-1", "event-2")]


def _unknown_character(candidate: StoryPlan) -> None:
    candidate.events[0].character_ids = ["unknown"]


def _unknown_object(candidate: StoryPlan) -> None:
    candidate.events[0].object_ids = ["unknown-object"]


def _duplicate_event_ids(candidate: StoryPlan) -> None:
    candidate.events[1].id = candidate.events[0].id


def _chapter_orders_not_consecutive(candidate: StoryPlan) -> None:
    candidate.chapters.append(second_chapter(order=3))
    candidate.events.append(event("event-4", 4, "chapter-2"))
    candidate.dependencies.append(dependency("event-3", "event-4"))


def _empty_chapter(candidate: StoryPlan) -> None:
    candidate.chapters.append(second_chapter())


def _event_order_breaks_chapter_order(candidate: StoryPlan) -> None:
    candidate.chapters.append(second_chapter())
    candidate.events.append(event("event-4", 4, "chapter-2"))
    candidate.dependencies.append(dependency("event-3", "event-4"))
    candidate.events[0].chapter_id = "chapter-2"
    candidate.events[3].chapter_id = "chapter-1"


def _self_referential_dependency(candidate: StoryPlan) -> None:
    candidate.dependencies.append(dependency("event-1", "event-1"))


def _duplicate_dependency(candidate: StoryPlan) -> None:
    candidate.dependencies.append(dependency("event-1", "event-2"))


def _only_temporal_dependencies(candidate: StoryPlan) -> None:
    candidate.dependencies = [
        dependency("event-1", "event-2", "temporal"),
        dependency("event-2", "event-3", "temporal"),
    ]


def _weakly_disconnected(candidate: StoryPlan) -> None:
    candidate.dependencies = [dependency("event-1", "event-2")]


def _unknown_payoff(candidate: StoryPlan) -> None:
    candidate.dependencies = [dependency("event-1", "event-2"), dependency("event-2", "event-3")]
    candidate.events[1].payoff_of = ["charcoal_note"]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (_cycle, "cycle"),
        (_backwards_dependency, "backwards"),
        (_unknown_character, "unknown characters"),
        (_unknown_object, "unknown objects"),
        (_duplicate_event_ids, "event ids"),
        (_chapter_orders_not_consecutive, "chapter orders must be consecutive"),
        (_empty_chapter, "chapters without events"),
        (_event_order_breaks_chapter_order, "follow chapter order"),
        (_self_referential_dependency, "self-referential"),
        (_duplicate_dependency, "unique"),
        (_only_temporal_dependencies, "causal"),
        (_weakly_disconnected, "weakly connected"),
        (_unknown_payoff, "unknown event IDs: charcoal_note"),
    ],
)
def test_structural_rejections(mutate, match) -> None:
    """Every objective invariant validate_story_plan enforces rejects with an ASCII message."""
    candidate = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    mutate(candidate)
    with pytest.raises(ValueError, match=match) as captured:
        validate_story_plan(candidate, world(), characters())
    assert str(captured.value).isascii()


def test_unknown_payoff_reports_the_allowed_earlier_events() -> None:
    """A payoff error names both the offending value and the events it could legally cite."""
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


def test_payoff_schema_distinguishes_event_ids_from_story_state() -> None:
    properties = PlotEvent.model_json_schema()["properties"]
    assert "earlier event" in properties["payoff_of"]["description"]
    assert "not IDs" in properties["effects"]["description"]


def profile_plan(event_count: int) -> StoryPlan:
    """Build a valid linear plan with the requested number of events."""
    candidate = plan([dependency("event-1", "event-2"), dependency("event-2", "event-3")])
    for order in range(4, event_count + 1):
        identifier = f"event-{order}"
        candidate.events.append(event(identifier, order))
        candidate.dependencies.append(dependency(f"event-{order - 1}", identifier))
    validate_story_plan(candidate, world(), characters())
    return candidate


@pytest.mark.parametrize(
    ("profile", "event_count", "expectation"),
    [
        (NarrativeProfile.ESSENTIAL, 3, "rejects"),
        (NarrativeProfile.ESSENTIAL, 4, "accepts"),
        (NarrativeProfile.DEVELOPED, 7, "rejects"),
        (NarrativeProfile.DEVELOPED, 8, "accepts"),
        (NarrativeProfile.EXPANSIVE, 9, "rejects"),
        (NarrativeProfile.EXPANSIVE, 10, "rejects-without-branch"),
    ],
    ids=[
        "essential-below-floor",
        "essential-at-floor",
        "developed-below-floor",
        "developed-at-floor",
        "expansive-below-floor",
        "expansive-linear-chain-lacks-a-branch",
    ],
)
def test_profile_structure(profile, event_count, expectation) -> None:
    """Each profile's event floor and, for Expansive, its branch-and-join contract."""
    if expectation == "accepts":
        validate_profile_structure(profile_plan(event_count), profile)
    elif expectation == "rejects":
        minimum = profile_event_floor(profile)
        with pytest.raises(
            ValueError,
            match=rf"{profile.value} profile requires at least {minimum} events; got {event_count}",
        ):
            validate_profile_structure(profile_plan(event_count), profile)
    else:
        with pytest.raises(ValueError, match="causal dependency branch"):
            validate_profile_structure(profile_plan(event_count), profile)


def test_a_chapter_carrying_a_single_event_is_rejected_for_every_profile() -> None:
    """The per-chapter floor is validated, so a stub chapter can no longer reach the writer."""
    for profile in NarrativeProfile:
        candidate = profile_plan(profile_event_floor(profile))
        third = second_chapter(order=3)
        third.id = "chapter-3"
        candidate.chapters.extend([second_chapter(), third])
        # chapter-2 keeps one event and chapter-3 none, so the message must name both in order.
        candidate.events[-1].chapter_id = "chapter-2"
        with pytest.raises(ValueError) as captured:
            validate_profile_structure(candidate, profile)
        message = str(captured.value)
        assert message.isascii()
        assert f"requires at least {MIN_EVENTS_PER_CHAPTER} events per chapter" in message
        assert "chapter-2, chapter-3" in message


def test_expansive_profile_accepts_a_causal_branch_and_later_join() -> None:
    candidate = profile_plan(10)
    candidate.dependencies = [
        dependency("event-1", "event-2"),
        dependency("event-1", "event-3"),
        dependency("event-2", "event-4"),
        dependency("event-3", "event-4"),
        *[dependency(f"event-{order}", f"event-{order + 1}") for order in range(4, 10)],
    ]
    validate_story_plan(candidate, world(), characters())
    validate_profile_structure(candidate, NarrativeProfile.EXPANSIVE)


def test_the_event_target_follows_from_the_chapter_band_and_never_undercuts_the_floor() -> None:
    assert profile_event_target(NarrativeProfile.ESSENTIAL) == (4, 6)
    assert profile_event_target(NarrativeProfile.DEVELOPED) == (8, 10)
    assert profile_event_target(NarrativeProfile.EXPANSIVE) == (10, 14)
    for profile in NarrativeProfile:
        low, high = profile_event_target(profile)
        low_chapters, high_chapters = profile_chapter_band(profile)
        floor = profile_min_events(profile) or 0
        # The target is what makes the chapter band and the validated floor compatible: aiming at
        # it satisfies validate_profile_structure, which aiming at the bare floor did not.
        assert low >= floor
        assert low >= low_chapters * MIN_EVENTS_PER_CHAPTER
        assert high >= high_chapters * MIN_EVENTS_PER_CHAPTER
        assert low <= high
        # The low end is the single number: taught to the planner and enforced on its plan.
        assert profile_event_floor(profile) == low
        assert low <= profile_event_aim(profile) <= high
