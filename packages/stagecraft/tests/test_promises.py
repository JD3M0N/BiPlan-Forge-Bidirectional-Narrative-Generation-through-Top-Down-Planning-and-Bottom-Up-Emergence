"""Invariants the promise ledger must satisfy against an already frozen plan."""

import pytest
from asg_stagecraft.pipeline import StoryPipeline
from asg_stagecraft.planning.graph import materialize_plan
from asg_stagecraft.planning.profiles import NarrativeProfile, promise_band
from asg_stagecraft.planning.promises import materialize_ledger
from asg_stagecraft.schemas import (
    PromiseContract,
    PromiseLedgerDraft,
    PromiseOpening,
    PromisePayoff,
    PromiseProgress,
)
from test_generator_v5 import make_characters, make_world, promise_ledger, valid_plan


def plan():
    """Build the two-chapter validated plan every case below annotates."""
    return materialize_plan(valid_plan(), make_world(), make_characters())


def ledger(**overrides) -> PromiseLedgerDraft:
    """Build the smallest valid essential ledger, with one field replaced when asked."""
    candidate = promise_ledger(valid_plan())
    for field, value in overrides.items():
        setattr(candidate, field, value)
    return candidate


def promise(
    identifier: str = "promise-x",
    *,
    kind: str = "character_conflict",
    opening: str = "event-1",
    progress: str = "event-2",
    payoff: str = "event-3",
    prepared_by: list[str] | None = None,
) -> PromiseContract:
    """Build one promise contract with every anchor under the caller's control."""
    return PromiseContract(
        id=identifier,
        kind=kind,
        subject="Ana against her own silence",
        dramatic_question="Will Ana speak?",
        opening=PromiseOpening(
            event_id=opening,
            signal="Ana says nothing.",
            reader_expectation="that she will have to speak",
        ),
        progress=[
            PromiseProgress(
                id=f"{identifier}-p1",
                event_id=progress,
                observable_delta="Ana answers a question she used to dodge.",
                new_cost_or_information="Her sister hears it.",
            )
        ],
        payoff=PromisePayoff(
            event_id=payoff,
            answer="Ana speaks in the square.",
            cost="Her sister stops speaking to her.",
            prepared_by_progress_ids=prepared_by or [f"{identifier}-p1"],
            surprising_without_breach="The silence she kept becomes the proof.",
        ),
    )


def test_a_valid_ledger_derives_its_chapters_from_the_plan() -> None:
    result = materialize_ledger(ledger(), plan(), NarrativeProfile.ESSENTIAL)

    assert result.chapter_by_event == {
        "event-1": "chapter-1",
        "event-2": "chapter-1",
        "event-3": "chapter-2",
        "event-4": "chapter-2",
    }
    assert result.observations == []
    assert [item.id for item in result.promises] == ["promise-1", "promise-2"]


def test_an_unknown_anchor_is_rejected_and_names_the_legal_ids() -> None:
    candidate = ledger()
    candidate.promises[1].progress[0].event_id = "event-99"

    with pytest.raises(ValueError) as captured:
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)

    assert "event-99" in str(captured.value)
    assert "allowed event IDs: event-1, event-2, event-3, event-4" in str(captured.value)


def test_a_payoff_before_its_opening_is_rejected() -> None:
    candidate = ledger()
    candidate.promises[1].opening.event_id = "event-2"
    candidate.promises[1].payoff.event_id = "event-1"

    with pytest.raises(ValueError, match="does not come after its opening event"):
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)


def test_a_progress_outside_the_span_is_rejected() -> None:
    candidate = ledger()
    candidate.promises[1].progress[0].event_id = "event-4"

    with pytest.raises(ValueError, match="is not between the opening event"):
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)


def test_preparation_may_only_come_from_the_promise_that_pays() -> None:
    candidate = ledger()
    candidate.promises[1].payoff.prepared_by_progress_ids = ["progress-1"]

    with pytest.raises(ValueError, match="claims preparation from progress-1"):
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)


def test_the_primary_promise_must_pay_off_in_the_final_chapter() -> None:
    candidate = ledger()
    candidate.promises[0].payoff.event_id = "event-2"

    with pytest.raises(ValueError, match="must pay off in the final chapter chapter-2"):
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)


def test_the_primary_promise_must_be_the_story_direction_promise() -> None:
    candidate = ledger()
    candidate.promises[0].kind = "tone"

    with pytest.raises(ValueError, match="must be the story_direction promise"):
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)


def test_an_unknown_primary_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="is not a promise of this ledger"):
        materialize_ledger(
            ledger(primary_promise_id="promise-9"), plan(), NarrativeProfile.ESSENTIAL
        )


def test_a_promise_opened_in_the_final_chapter_is_rejected() -> None:
    candidate = ledger()
    candidate.promises[1].opening.event_id = "event-3"
    candidate.promises[1].progress[0].event_id = "event-4"
    candidate.promises[1].payoff.event_id = "event-4"

    with pytest.raises(ValueError, match="in the final chapter chapter-2"):
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)


def test_repeated_identifiers_are_rejected() -> None:
    candidate = ledger()
    candidate.promises[1].id = "promise-1"

    with pytest.raises(ValueError, match="promise IDs must be unique; repeated: promise-1"):
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)


def test_repeated_progress_identifiers_are_rejected() -> None:
    candidate = ledger()
    candidate.promises[1].progress[0].id = "progress-1"
    candidate.promises[1].payoff.prepared_by_progress_ids = ["progress-1"]

    with pytest.raises(ValueError, match="progress IDs must be unique"):
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)


def test_too_few_promises_for_the_profile_are_rejected() -> None:
    low = promise_band(NarrativeProfile.DEVELOPED)[0]

    with pytest.raises(ValueError, match=f"developed profile requires at least {low} promises"):
        materialize_ledger(ledger(), plan(), NarrativeProfile.DEVELOPED)


def test_more_promises_than_the_ending_can_pay_are_rejected() -> None:
    candidate = ledger()
    candidate.promises = [candidate.promises[0]] + [
        promise(f"promise-{index}") for index in range(2, 6)
    ]

    with pytest.raises(ValueError, match="allows at most 3 promises"):
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)


def test_a_payoff_that_ignores_its_events_declared_setup_is_only_observed() -> None:
    materialized = plan()
    paying = next(event for event in materialized.events if event.id == "event-4")
    paying.payoff_of = ["event-2"]

    result = materialize_ledger(ledger(), materialized, NarrativeProfile.ESSENTIAL)

    assert result.observations == [
        "promise promise-1 pays off on event-4, whose declared setups are event-2, but it "
        "opened on event-1"
    ]


@pytest.mark.parametrize(
    "break_it",
    [
        lambda item: setattr(item.promises[1].progress[0], "event_id", "event-99"),
        lambda item: setattr(item.promises[1].payoff, "event_id", "event-1"),
        lambda item: setattr(item.promises[0].payoff, "event_id", "event-2"),
        lambda item: setattr(item.promises[0], "kind", "tone"),
        lambda item: setattr(item.promises[1], "id", "promise-1"),
        lambda item: setattr(item, "primary_promise_id", "promise-9"),
    ],
)
def test_every_rejection_is_ascii_and_reaches_a_repair_block(break_it, tmp_path) -> None:
    """No message this validator can raise may reach the model as unreadable repair guidance."""
    candidate = ledger()
    break_it(candidate)

    with pytest.raises(ValueError) as captured:
        materialize_ledger(candidate, plan(), NarrativeProfile.ESSENTIAL)

    issue = str(captured.value)
    assert issue.isascii()
    pipeline = StoryPipeline(None, tmp_path)
    pipeline.repository = _RecordingRepository()
    feedback = pipeline._record_rejected_ledger(candidate, 1, ValueError(issue), plan())
    assert issue in feedback
    assert "LEDGER REPAIR REQUIRED" in feedback
    assert feedback.isascii()


class _RecordingRepository:
    """Stand in for ArtifactRepository while a rejection block is being built."""

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self.saved = {}

    def save_data(self, filename, value) -> None:
        """Record one rejected candidate instead of writing it to disk."""
        self.saved[filename] = value
