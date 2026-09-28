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


def _unknown_anchor(item) -> None:
    item.promises[1].progress[0].event_id = "event-99"


def _payoff_before_opening(item) -> None:
    item.promises[1].opening.event_id = "event-2"
    item.promises[1].payoff.event_id = "event-1"


def _progress_outside_span(item) -> None:
    item.promises[1].progress[0].event_id = "event-4"


def _preparation_from_another_promise(item) -> None:
    item.promises[1].payoff.prepared_by_progress_ids = ["progress-1"]


def _primary_not_paying_off_in_final_chapter(item) -> None:
    item.promises[0].payoff.event_id = "event-2"


def _primary_not_story_direction(item) -> None:
    item.promises[0].kind = "tone"


def _unknown_primary_id(item) -> None:
    item.primary_promise_id = "promise-9"


def _promise_opened_in_final_chapter(item) -> None:
    item.promises[1].opening.event_id = "event-3"
    item.promises[1].progress[0].event_id = "event-4"
    item.promises[1].payoff.event_id = "event-4"


def _repeated_promise_id(item) -> None:
    item.promises[1].id = "promise-1"


def _repeated_progress_id(item) -> None:
    item.promises[1].progress[0].id = "progress-1"
    item.promises[1].payoff.prepared_by_progress_ids = ["progress-1"]


def _too_many_promises(item) -> None:
    item.promises = [item.promises[0]] + [promise(f"promise-{index}") for index in range(2, 6)]


_DEVELOPED_FLOOR = promise_band(NarrativeProfile.DEVELOPED)[0]


@pytest.mark.parametrize(
    ("mutate", "profile", "expected"),
    [
        (
            _unknown_anchor,
            NarrativeProfile.ESSENTIAL,
            ("event-99", "allowed event IDs: event-1, event-2, event-3, event-4"),
        ),
        (
            _payoff_before_opening,
            NarrativeProfile.ESSENTIAL,
            ("does not come after its opening event",),
        ),
        (_progress_outside_span, NarrativeProfile.ESSENTIAL, ("is not between the opening event",)),
        (
            _preparation_from_another_promise,
            NarrativeProfile.ESSENTIAL,
            ("claims preparation from progress-1",),
        ),
        (
            _primary_not_paying_off_in_final_chapter,
            NarrativeProfile.ESSENTIAL,
            ("must pay off in the final chapter chapter-2",),
        ),
        (
            _primary_not_story_direction,
            NarrativeProfile.ESSENTIAL,
            ("must be the story_direction promise",),
        ),
        (
            _unknown_primary_id,
            NarrativeProfile.ESSENTIAL,
            ("is not a promise of this ledger",),
        ),
        (
            _promise_opened_in_final_chapter,
            NarrativeProfile.ESSENTIAL,
            ("in the final chapter chapter-2",),
        ),
        (
            _repeated_promise_id,
            NarrativeProfile.ESSENTIAL,
            ("promise IDs must be unique; repeated: promise-1",),
        ),
        (
            _repeated_progress_id,
            NarrativeProfile.ESSENTIAL,
            ("progress IDs must be unique",),
        ),
        (
            lambda item: None,
            NarrativeProfile.DEVELOPED,
            (f"developed profile requires at least {_DEVELOPED_FLOOR} promises",),
        ),
        (
            _too_many_promises,
            NarrativeProfile.ESSENTIAL,
            ("allows at most 3 promises",),
        ),
    ],
)
def test_ledger_rejections_are_ascii_and_reach_a_repair_block(
    mutate, profile, expected, tmp_path
) -> None:
    """Every objective invariant materialize_ledger enforces, and that its repair loop can read."""
    candidate = ledger()
    mutate(candidate)

    with pytest.raises(ValueError) as captured:
        materialize_ledger(candidate, plan(), profile)

    issue = str(captured.value)
    for fragment in expected:
        assert fragment in issue
    assert issue.isascii()

    pipeline = StoryPipeline(None, tmp_path)
    pipeline.repository = _RecordingRepository()
    feedback = pipeline._record_rejected_ledger(candidate, 1, ValueError(issue), plan())
    assert issue in feedback
    assert "LEDGER REPAIR REQUIRED" in feedback
    assert feedback.isascii()


def test_a_payoff_that_ignores_its_events_declared_setup_is_only_observed() -> None:
    materialized = plan()
    paying = next(event for event in materialized.events if event.id == "event-4")
    paying.payoff_of = ["event-2"]

    result = materialize_ledger(ledger(), materialized, NarrativeProfile.ESSENTIAL)

    assert result.observations == [
        "promise promise-1 pays off on event-4, whose declared setups are event-2, but it "
        "opened on event-1"
    ]


class _RecordingRepository:
    """Stand in for ArtifactRepository while a rejection block is being built."""

    def __init__(self) -> None:
        """Start with nothing recorded."""
        self.saved = {}

    def save_data(self, filename, value) -> None:
        """Record one rejected candidate instead of writing it to disk."""
        self.saved[filename] = value
