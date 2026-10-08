"""Compatibility facade and baseline rendering for narrative skeleton guidance."""

from ..schemas import NarrativeBlueprint
from .catalog import PLOT_SKELETONS as PLOT_SKELETONS
from .catalog import SKELETONS_BY_ID as SKELETONS_BY_ID
from .catalog_types import FunctionalRole as FunctionalRole
from .catalog_types import Layer as Layer
from .catalog_types import PlotSkeleton as PlotSkeleton

PERSONA_SUGGESTIONS: tuple[str, ...] = (
    "wizard",
    "detective",
    "thief",
    "scientist",
    "king",
    "outsider",
    "monster",
    "soldier",
    "healer",
    "exile",
    "scholar",
    "smuggler",
    "priest",
    "artist",
    "merchant",
    "engineer",
    "hunter",
    "spy",
    "judge",
    "servant",
    "heir",
    "rebel",
    "nomad",
    "caretaker",
    "gambler",
    "journalist",
    "sailor",
    "farmer",
    "prisoner",
    "child",
)


FALLBACK_SHORTLIST: tuple[str, ...] = (
    "quest",
    "mystery",
    "transformation",
    "love",
    "underdog",
    "discovery",
    "fall",
    "comedy",
)


def _validate_catalog() -> None:
    """Fail at import time when the catalog references skeletons that do not exist."""
    if len(SKELETONS_BY_ID) != len(PLOT_SKELETONS):
        raise ValueError("plot skeleton ids must be unique")
    for item in PLOT_SKELETONS:
        for reference in (*item.pairs_well_with, *item.tensions_with):
            if reference not in SKELETONS_BY_ID:
                raise ValueError(f"skeleton {item.id} references unknown skeleton {reference}")
            if reference == item.id:
                raise ValueError(f"skeleton {item.id} cannot reference itself")
    for reference in FALLBACK_SHORTLIST:
        if reference not in SKELETONS_BY_ID:
            raise ValueError(f"fallback shortlist references unknown skeleton {reference}")


_validate_catalog()


def find_skeleton(skeleton_id: str) -> PlotSkeleton | None:
    """Return one catalog entry, or None when the id is unknown."""
    return SKELETONS_BY_ID.get(skeleton_id)


def functional_role_vocabulary() -> list[str]:
    """Return the preferred functional-role words offered to the character designer."""
    return [role.value for role in FunctionalRole]


def _bullet_list(values: tuple[str, ...] | list[str]) -> str:
    """Join short phrases into one readable inline list."""
    return "; ".join(values)


def blueprint_guidance(blueprint: NarrativeBlueprint) -> str:
    """Render one blueprint as explicitly optional inspiration for a downstream agent."""
    macroplot = find_skeleton(blueprint.macroplot_id)
    found_subplots = (find_skeleton(item) for item in blueprint.subplot_ids)
    subplots = [item for item in found_subplots if item]
    macroplot_name = macroplot.name if macroplot else blueprint.macroplot_id
    subplot_names = ", ".join(item.name for item in subplots) or "none in particular"

    questions: list[str] = []
    movements: list[str] = []
    for item in ([macroplot] if macroplot else []) + subplots:
        questions.extend(item.pressure_questions)
        movements.extend(item.possible_movements)

    lines = [
        "NARRATIVE INSPIRATION (non-binding):",
        (
            f"This premise resonates with the macroplot {macroplot_name} and possible subplots "
            f"{subplot_names}. This is raw material, not a structure to fill in."
        ),
        f"Reading of the premise: {blueprint.macroplot_reading}",
    ]
    if questions:
        lines.append(f"Open tensions: {_bullet_list(questions)}")
    if movements:
        lines.append(
            "Movements that sometimes appear (reorder, invert, or ignore any of them): "
            f"{_bullet_list(movements)}"
        )
    if blueprint.unexpected_angle:
        lines.append(f"Deliberate deviation to explore: {blueprint.unexpected_angle}")
    for suggestion in blueprint.role_suggestions:
        lines.append(
            f"Role suggestion: {suggestion.functional_role} / {suggestion.persona} - "
            f"{suggestion.sketch}"
        )
    lines.append(
        "Attach role suggestions only where they sharpen a character that already exists. "
        "You may honour, subvert, or discard this section entirely. Never add a scene only to "
        "satisfy it, never name these labels in the fiction, and never let it override the STORY "
        "SPECIFICATION or the NARRATIVE PROFILE CONTRACT."
    )
    return "\n".join(lines)
