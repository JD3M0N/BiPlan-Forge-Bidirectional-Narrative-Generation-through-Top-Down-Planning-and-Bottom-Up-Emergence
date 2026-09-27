"""Pure Markdown rendering for a validated theater script.

Follows the classic printed-play convention ("SPEAKER.-text", using an em dash in the actual
output) and uses only the three heading levels the code itself emits. No emphasis markers
(asterisk or underscore): Telegram escapes everything that is not a heading, the
text-to-speech reader strips Markdown markers but not their characters, and the
blind-comparison HTML would show them literally.
"""

from __future__ import annotations

from ..schemas import ActScript, PlayScript, ScriptLine, ScriptScene

_ROMAN = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


def roman(number: int) -> str:
    """Render a positive integer as an uppercase Roman numeral."""
    remaining = number
    pieces: list[str] = []
    for value, symbol in _ROMAN:
        count, remaining = divmod(remaining, value)
        pieces.append(symbol * count)
    return "".join(pieces)


def render_script(play: PlayScript) -> str:
    """Render the complete play as one Markdown document."""
    names = {member.character_id: member.name for member in play.cast}
    sections = [f"# {play.title}"]
    if play.cast:
        sections.append(_render_cast(play))
    sections.extend(
        render_act(act, scene_label=play.scene_label, act_label=play.act_label, names=names)
        for act in play.acts
    )
    return "\n\n".join(sections)


def _render_cast(play: PlayScript) -> str:
    """Render the dramatis personae as a Markdown list, one entry per on-stage character."""
    lines = [f"## {play.cast_heading}"]
    for member in play.cast:
        entry = f"- {member.name.upper()}"
        description = member.description.strip()
        # A description that already ends its sentence keeps its own stop; the 25-09 scripts
        # printed ".." on every entry because a period was always added.
        if description and description[-1] not in ".!?…":
            description = f"{description}."
        lines.append(f"{entry}, {description}" if description else f"{entry}.")
    return "\n".join(lines)


def render_act(
    act: ActScript,
    *,
    scene_label: str,
    act_label: str = "",
    names: dict[str, str] | None = None,
) -> str:
    """Render one act as a Markdown section, one subsection per scene.

    ``names`` maps character IDs to their printed names; a scene rendered without the play's
    cast list (such as a draft act on its own) falls back to the uppercased character ID.
    """
    labels = names or {}
    heading = f"## {act_label} {roman(act.number)}. {act.title}" if act_label else f"## {act.title}"
    scenes = [_render_scene(scene, scene_label=scene_label, names=labels) for scene in act.scenes]
    return "\n\n".join([heading, *scenes])


def _render_scene(scene: ScriptScene, *, scene_label: str, names: dict[str, str]) -> str:
    """Render one scene: its opening direction, then every line in order."""
    blocks = [f"### {scene_label} {scene.number}", f"({scene.setting})"]
    blocks.extend(_render_line(line, names) for line in scene.lines)
    return "\n\n".join(blocks)


def _render_line(line: ScriptLine, names: dict[str, str]) -> str:
    """Render one dialogue or stage-direction line in the printed-play convention."""
    if line.kind == "direction":
        return f"({line.text})"
    label = names.get(line.speaker_id, line.speaker_id).upper()
    parenthetical = f"({line.parenthetical}) " if line.parenthetical else ""
    return f"{label}.—{parenthetical}{line.text}"


def staging_index(play: PlayScript) -> str:
    """Render the staging summary the script critic reads, in place of the full text.

    Never shows a scene ID: a critic that echoed one into a revision note's event_ids would
    make _validate_note_references reject the whole critique.
    """
    names = {member.character_id: member.name for member in play.cast}
    lines = []
    for act in play.acts:
        for scene in act.scenes:
            cast = ", ".join(
                f"{names.get(member.character_id, member.character_id)} (wants: {member.objective})"
                for member in scene.cast
            )
            events = ", ".join(scene.event_ids)
            location = scene.location_id or "(none)"
            lines.append(
                f"act {act.chapter_id}, scene {scene.number} | events: {events} | "
                f"location: {location} | cast: {cast}"
            )
    return "\n".join(lines)


__all__ = ["render_act", "render_script", "roman", "staging_index"]
