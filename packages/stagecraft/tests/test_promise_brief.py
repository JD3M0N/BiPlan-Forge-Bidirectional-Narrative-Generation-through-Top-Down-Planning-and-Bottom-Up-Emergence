"""What the ledger renders into a prompt, and what it must never render."""

from asg_stagecraft.planning.graph import materialize_plan
from asg_stagecraft.planning.profiles import NarrativeProfile, promise_band
from asg_stagecraft.planning.promise_brief import (
    chapter_brief,
    critic_obligations,
    event_index,
    rendered_ledger,
)
from asg_stagecraft.planning.promises import materialize_ledger
from test_generator_v5 import make_characters, make_world, promise_ledger, valid_plan


def built():
    """Build one validated plan and the rendered ledger drawn over it."""
    plan = materialize_plan(valid_plan(), make_world(), make_characters())
    ledger = materialize_ledger(promise_ledger(valid_plan()), plan, NarrativeProfile.ESSENTIAL)
    return plan, rendered_ledger(ledger, plan)


def events_of(plan, chapter_id):
    """List the events one chapter owns, in the order the plan trusts."""
    by_id = {event.id: event for event in plan.events}
    return [by_id[item] for item in plan.topological_order if by_id[item].chapter_id == chapter_id]


def test_a_chapter_is_only_told_about_its_own_events() -> None:
    plan, ledger = built()

    for chapter in plan.chapters:
        owned = {event.id for event in events_of(plan, chapter.id)}
        block = chapter_brief(ledger, chapter, events_of(plan, chapter.id))
        cited = {line.split(" | ")[0].removeprefix("- ") for line in block.splitlines()[1:]}
        assert cited
        assert cited <= owned


def test_a_chapter_that_owes_nothing_gets_no_block() -> None:
    plan, ledger = built()
    idle = plan.chapters[0]

    assert chapter_brief(ledger, idle, []) == ""
    assert chapter_brief(None, idle, events_of(plan, idle.id)) == ""


def test_the_blocks_stored_on_the_ledger_are_the_ones_that_travel() -> None:
    plan, ledger = built()

    for chapter in plan.chapters:
        assert ledger.chapter_blocks[chapter.id] == chapter_brief(
            ledger, chapter, events_of(plan, chapter.id)
        )
    assert ledger.critic_block == critic_obligations(ledger)


def test_no_promise_count_or_profile_figure_reaches_any_block() -> None:
    plan, ledger = built()
    low, high = promise_band(NarrativeProfile.ESSENTIAL)
    rendered = "\n".join([*ledger.chapter_blocks.values(), ledger.critic_block])

    for figure in {low, high, len(ledger.promises)}:
        assert f"{figure} promises" not in rendered
    assert "profile" not in rendered.casefold()


def test_the_primary_promise_leads_every_rendering() -> None:
    _, ledger = built()

    obligations = critic_obligations(ledger)
    assert "promise-1 (primary)" in obligations
    assert obligations.index("promise-1") < obligations.index("promise-2")
    assert critic_obligations(None) == ""


def test_the_event_index_offers_exactly_the_legal_anchors() -> None:
    plan, _ = built()
    index = event_index(plan)

    assert [line.split(" | ")[0].removeprefix("- ") for line in index.splitlines()] == [
        "event-1",
        "event-2",
        "event-3",
        "event-4",
    ]
    assert "chapter chapter-1" in index
