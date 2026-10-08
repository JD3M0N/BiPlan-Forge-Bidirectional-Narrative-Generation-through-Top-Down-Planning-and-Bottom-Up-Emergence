"""Render compact, audience-specific inspiration from validated narrative choices."""

from .guidance_models import CompositionDraft

_BOUNDARY = (
    "This is optional inspiration. Honour, subvert, or discard it. Never override the STORY "
    "SPECIFICATION or NARRATIVE PROFILE CONTRACT, introduce a scene merely to satisfy a pattern, "
    "or name the pattern labels in the fiction."
)


def render_blocks(draft: CompositionDraft) -> tuple[str, str]:
    """Render only selected contributions, not every generic movement in their source entries."""
    if draft.abstained:
        return "", ""
    shared = ["NARRATIVE INSPIRATION (non-binding):", f"Reading: {draft.reason}"]
    character = [*shared]
    planning = [*shared]
    for selection in draft.selections:
        line = f"{selection.scope.capitalize()} contribution: {selection.contribution}"
        if selection.connection:
            line += f" Connection to the central conflict: {selection.connection}"
        character.append(line)
        planning.append(line)
    for role in draft.role_suggestions:
        appearance = f" / {role.persona}" if role.persona else ""
        character.append(
            f"Possible function: {role.functional_role.value}{appearance}: {role.sketch}"
        )
    for question in draft.questions:
        character.append(f"Open tension: {question.adaptation}")
        planning.append(f"Open tension: {question.adaptation}")
    for movement in draft.movements:
        planning.append(f"Possible movement: {movement.adaptation}")
    if draft.deviation:
        line = f"Optional departure: {draft.deviation.proposal}"
        character.append(line)
        planning.append(line)
    character.extend(["Attach suggestions only to characters the premise warrants.", _BOUNDARY])
    planning.append(_BOUNDARY)
    return "\n".join(character), "\n".join(planning)
