"""Shared qualitative narrative-profile contracts."""

from __future__ import annotations

from enum import StrEnum


class NarrativeProfile(StrEnum):
    """Describe narrative depth without imposing numeric prose-length budgets."""

    ESSENTIAL = "essential"
    DEVELOPED = "developed"
    EXPANSIVE = "expansive"


PROFILE_LABELS: dict[NarrativeProfile, str] = {
    NarrativeProfile.ESSENTIAL: "Esencial",
    NarrativeProfile.DEVELOPED: "Desarrollada",
    NarrativeProfile.EXPANSIVE: "Expansiva",
}


# Purely qualitative on purpose. Event counts live in profile_event_target and reach the planner
# from there: this text ships inside every agent prompt, so a number here competed with the
# planner's own and the model followed this one, pinning Expansive plans to nine events.
PROFILE_GUIDANCE: dict[NarrativeProfile, str] = {
    NarrativeProfile.ESSENTIAL: (
        "Keep one focused central conflict, a lean cast, direct causal progression, and no "
        "optional subplots. Every chapter and event must materially advance the main dramatic "
        "line."
    ),
    NarrativeProfile.DEVELOPED: (
        "Build a complete central arc with escalating complications, a functional secondary arc, "
        "purposeful supporting-character development, deliberate setup and payoff, and balanced "
        "dramatic progression. Every event must change conflict, knowledge, relationships, "
        "resources, stakes, or consequences rather than split one unchanged action into smaller "
        "pieces."
    ),
    NarrativeProfile.EXPANSIVE: (
        "Build a layered main plot with meaningful subplots, multiple interacting character arcs, "
        "branching and rejoining causal developments, rich world consequences, and patient scene "
        "development. Plan a real causal branch and a later causal join: one earlier event must "
        "cause at least two later paths through two outgoing causal dependencies, and a "
        "subsequent event must reunite paths through at least two incoming causal dependencies. "
        "Independent parallel roots do not constitute a branch. Every event must change conflict, "
        "knowledge, relationships, resources, stakes, or consequences rather than split one "
        "unchanged action into smaller pieces. Give every major event and each subplot turn "
        "enough scene space for action, reaction, and consequence; do not pack several planned "
        "events into a brief summary passage or rush their causal reunion."
    ),
}


# The floor each profile owes its own contract, independent of how the chapter band is drawn.
# It no longer binds on its own (6 < 8 and 9 < 10): profile_event_target reconciles it with the
# band and validate_profile_structure enforces that. It survives as the guard that keeps a
# narrower chapter band from silently sinking a profile below its contract.
PROFILE_MIN_EVENTS: dict[NarrativeProfile, int | None] = {
    NarrativeProfile.ESSENTIAL: None,
    NarrativeProfile.DEVELOPED: 6,
    NarrativeProfile.EXPANSIVE: 9,
}


# Structural chapter bands. No validator enforces the band itself, but it sets the event target
# through MIN_EVENTS_PER_CHAPTER, and that target's low end is the validated floor.
PROFILE_CHAPTER_BAND: dict[NarrativeProfile, tuple[int, int]] = {
    NarrativeProfile.ESSENTIAL: (2, 3),
    NarrativeProfile.DEVELOPED: (4, 5),
    NarrativeProfile.EXPANSIVE: (5, 7),
}


# A chapter carrying a single event reads as a stub rather than a scene, so this is a validated
# invariant, not advice. Measured Expansive runs left 42% of chapters that way while the planner
# aimed at the bare event floor, which the chapter band cannot satisfy: 5 chapters with two events
# each already need 10, not 9.
MIN_EVENTS_PER_CHAPTER = 2


def profile_guidance(profile: NarrativeProfile) -> str:
    """Return the canonical downstream contract for one profile."""
    return PROFILE_GUIDANCE[profile]


def profile_min_events(profile: NarrativeProfile) -> int | None:
    """Return the profile's own event floor, before the chapter band is taken into account."""
    return PROFILE_MIN_EVENTS[profile]


def profile_chapter_band(profile: NarrativeProfile) -> tuple[int, int]:
    """Return the advisory minimum and maximum chapter count for a narrative profile."""
    return PROFILE_CHAPTER_BAND[profile]


def profile_event_target(profile: NarrativeProfile) -> tuple[int, int]:
    """Return the event range the chapter band implies at the per-chapter event floor."""
    low_chapters, high_chapters = profile_chapter_band(profile)
    minimum = profile_min_events(profile) or 0
    low = max(low_chapters * MIN_EVENTS_PER_CHAPTER, minimum)
    return low, max(high_chapters * MIN_EVENTS_PER_CHAPTER, low)


def profile_event_floor(profile: NarrativeProfile) -> int:
    """Return the one event count that is both taught to the planner and enforced on its plan."""
    return profile_event_target(profile)[0]


def profile_event_aim(profile: NarrativeProfile) -> int:
    """Return the event count the planner is told to aim at, away from the rejection boundary."""
    low, high = profile_event_target(profile)
    return (low + high) // 2
