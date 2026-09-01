"""Shared qualitative narrative-profile contracts."""

from __future__ import annotations

from enum import StrEnum


class NarrativeProfile(StrEnum):
    """Describe narrative depth without imposing numeric budgets."""

    ESSENTIAL = "essential"
    DEVELOPED = "developed"
    EXPANSIVE = "expansive"


PROFILE_LABELS: dict[NarrativeProfile, str] = {
    NarrativeProfile.ESSENTIAL: "Esencial",
    NarrativeProfile.DEVELOPED: "Desarrollada",
    NarrativeProfile.EXPANSIVE: "Expansiva",
}


PROFILE_GUIDANCE: dict[NarrativeProfile, str] = {
    NarrativeProfile.ESSENTIAL: (
        "Keep one focused central conflict, a lean cast, direct causal progression, and no "
        "optional subplots. Every chapter and event must materially advance the main dramatic line."
    ),
    NarrativeProfile.DEVELOPED: (
        "Build a complete central arc with escalating complications, purposeful supporting-character "
        "development, deliberate setup and payoff, and balanced dramatic progression."
    ),
    NarrativeProfile.EXPANSIVE: (
        "Build a layered main plot with meaningful subplots, multiple interacting character arcs, "
        "branching and rejoining causal developments, rich world consequences, and patient scene development."
    ),
}


def profile_guidance(profile: NarrativeProfile) -> str:
    """Return the canonical downstream contract for one profile."""
    return PROFILE_GUIDANCE[profile]
