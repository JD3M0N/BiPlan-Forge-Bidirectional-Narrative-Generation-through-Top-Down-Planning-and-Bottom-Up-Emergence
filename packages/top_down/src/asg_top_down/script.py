"""Deterministic validation of one act's staging against the frozen plan.

Every ValueError message raised here stays in English on purpose, exactly as in graph.py and
promises.py: pipeline.py's script stages reinject it verbatim, together with the act anchor
index, into the model's act-repair prompt. It is part of the contract with the model, not
user-facing text.

An act never authors a plot event. Every scene cites the IDs of PlotEvents the validated plan
already contains, so the checks below decide staging against the plan's own order and
references instead of trusting what the model says about itself. This mirrors the ledger's
"cite, never invent" contract in promises.py, applied to staging instead of promises.

Normalize more, reject less: a stage direction's speaker_id and parenthetical, a dialogue
line's actor_ids, wrapping parentheses, and duplicate cast or event IDs are all silently
corrected in _normalize_scene/_normalize_line before any rule below runs, because each has
exactly one correct fix and rejecting them would only spend an attempt on a shape the model
could not have meant two ways.
"""

from __future__ import annotations

import re

from .formats import ScriptMethod
from .schemas import (
    ActScript,
    ActScriptDraft,
    CastNote,
    ChapterPlan,
    CharactersArtifact,
    PlayCastMember,
    PlayScript,
    PlotEvent,
    RevisionNote,
    ScriptFrame,
    ScriptLine,
    ScriptPresentation,
    ScriptScene,
    ScriptSceneDraft,
    StoryPlan,
    WorldArtifact,
    WriterCandidateDiagnostic,
)

_LEADING_DASHES = "—–-"
_WHITESPACE = re.compile(r"\s+")


def materialize_act(
    draft: ActScriptDraft,
    *,
    chapter: ChapterPlan,
    number: int,
    plan: StoryPlan,
    world: WorldArtifact,
    characters: CharactersArtifact,
) -> ActScript:
    """Validate one proposed act against the frozen plan and mint the trusted version."""
    chapter_events = _chapter_events(plan, chapter)
    scenes = [_normalize_scene(scene) for scene in draft.scenes]
    known_event_ids = {event.id for event in plan.events}
    chapter_event_ids = {event.id for event in chapter_events}
    positions = {event.id: index for index, event in enumerate(chapter_events)}
    known_locations = {location.id for location in world.locations}
    event_location = {event.id: event.location_id for event in chapter_events if event.location_id}
    known_characters = {character.id for character in characters.characters}

    _validate_events_known(scenes, known_event_ids)
    _validate_events_in_chapter(scenes, chapter_event_ids, plan)
    scenes = [_sorted_scene(scene, positions) for scene in scenes]
    _validate_plan_order(scenes, positions, chapter_event_ids)
    _validate_full_coverage(scenes, chapter_event_ids)
    scenes = [_filled_location(scene, event_location) for scene in scenes]
    _validate_known_locations(scenes, known_locations)
    _validate_scene_location_agreement(scenes, event_location)
    _validate_cast_known(scenes, known_characters)
    _validate_dialogue_speakers(scenes)
    _validate_direction_lines(scenes)
    _validate_has_dialogue(scenes)

    observations = _observations(scenes, chapter_events)
    minted = [
        ScriptScene(**scene.model_dump(), id=f"{chapter.id}-scene-{index}", number=index)
        for index, scene in enumerate(scenes, 1)
    ]
    return ActScript(
        chapter_id=chapter.id,
        number=number,
        title=chapter.title,
        scenes=minted,
        observations=observations,
    )


def act_anchor_index(
    chapter: ChapterPlan,
    plan: StoryPlan,
    world: WorldArtifact,
    characters: CharactersArtifact,
) -> str:
    """Render the only IDs one act may cite, in the exact order they must be staged."""
    events = _chapter_events(plan, chapter)
    locations_by_id = {location.id: location.name for location in world.locations}
    characters_by_id = {character.id: character.name for character in characters.characters}
    lines = [f"ACT ANCHOR INDEX ({chapter.id}). Cite only these IDs."]
    lines.append("EVENTS, in the only order they may be staged:")
    for event in events:
        location = "(none declared)" if not event.location_id else event.location_id
        participants = ", ".join(event.character_ids) or "(none)"
        lines.append(
            f"- {event.id} | location {location} | participants: {participants} | "
            f"{event.title}: {event.purpose}"
        )
    locations_line = ", ".join(f"{lid} ({name})" for lid, name in sorted(locations_by_id.items()))
    characters_line = ", ".join(f"{cid} ({name})" for cid, name in sorted(characters_by_id.items()))
    lines.append(f"LOCATIONS: {locations_line}")
    lines.append(f"CHARACTERS: {characters_line}")
    return "\n".join(lines)


def normalized_frame(frame: ScriptFrame, characters: CharactersArtifact) -> ScriptFrame:
    """Drop cast notes for unknown characters and deduplicate the rest, keeping the first."""
    known = {character.id for character in characters.characters}
    seen: set[str] = set()
    cast: list[CastNote] = []
    for note in frame.cast:
        if note.character_id not in known or note.character_id in seen:
            continue
        seen.add(note.character_id)
        cast.append(note)
    return frame.model_copy(update={"cast": cast})


def assemble_play(
    presentation: ScriptPresentation,
    characters: CharactersArtifact,
    acts: list[ActScript],
    *,
    language: str,
    method: ScriptMethod,
) -> PlayScript:
    """Assemble the complete theater-script contract from validated acts."""
    names_by_id = {character.id: character.name for character in characters.characters}
    descriptions_by_id = {note.character_id: note.description for note in presentation.frame.cast}
    on_stage: list[str] = []
    seen: set[str] = set()
    for act in acts:
        for scene in act.scenes:
            for member in scene.cast:
                if member.character_id not in seen:
                    seen.add(member.character_id)
                    on_stage.append(member.character_id)
    cast = [
        PlayCastMember(
            character_id=character_id,
            name=names_by_id.get(character_id, character_id),
            description=descriptions_by_id.get(character_id, ""),
        )
        for character_id in on_stage
    ]
    return PlayScript(
        title=presentation.title,
        language=language,
        script_method=method,
        cast_heading=presentation.frame.cast_heading,
        act_label=presentation.frame.act_label,
        scene_label=presentation.frame.scene_label,
        cast=cast,
        acts=acts,
    )


def revision_issue(
    candidate: ActScriptDraft,
    original: ActScript,
    notes: list[RevisionNote],
    *,
    chapter: ChapterPlan,
    number: int,
    plan: StoryPlan,
    world: WorldArtifact,
    characters: CharactersArtifact,
) -> tuple[ActScript | None, WriterCandidateDiagnostic | None]:
    """Return the first valid revised act, or explain why the candidate cannot replace it."""
    try:
        revised = materialize_act(
            candidate,
            chapter=chapter,
            number=number,
            plan=plan,
            world=world,
            characters=characters,
        )
    except ValueError as exc:
        return None, WriterCandidateDiagnostic(
            code="INVALID_SCRIPT_ACT",
            message=str(exc),
            retry_instruction="Return a complete act that satisfies every staging rule.",
            actual_words=0,
        )
    significant = any(note.priority in {"critical", "major"} for note in notes)
    if significant and revised.as_draft() == original.as_draft():
        return None, WriterCandidateDiagnostic(
            code="UNCHANGED_SIGNIFICANT_NOTES",
            message="the act is unchanged despite critical or major revision notes",
            retry_instruction="Apply every critical and major note with visible staging changes.",
            actual_words=0,
        )
    return revised, None


def _chapter_events(plan: StoryPlan, chapter: ChapterPlan) -> list[PlotEvent]:
    """Return this chapter's events in the plan's single trusted order."""
    if plan.topological_order:
        positions = {event_id: index for index, event_id in enumerate(plan.topological_order)}
    else:
        positions = {event.id: event.order for event in plan.events}
    events = [event for event in plan.events if event.chapter_id == chapter.id]
    return sorted(events, key=lambda event: positions.get(event.id, event.order))


def _clean_text(value: str) -> str:
    """Collapse whitespace and strip a leading Markdown heading marker."""
    stripped = _WHITESPACE.sub(" ", value).strip()
    return stripped.lstrip("#").strip()


def _unwrap(value: str) -> str:
    """Strip a single layer of wrapping parentheses the model added on its own."""
    stripped = value.strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        return stripped[1:-1].strip()
    return stripped


def _normalize_scene(scene: ScriptSceneDraft) -> ScriptSceneDraft:
    """Clean cosmetic drift without rejecting the scene: whitespace, stray markers, duplicates."""
    setting = _unwrap(_clean_text(scene.setting))
    lines = [_normalize_line(line) for line in scene.lines]
    seen_cast: set[str] = set()
    cast = []
    for member in scene.cast:
        if member.character_id in seen_cast:
            continue
        seen_cast.add(member.character_id)
        cast.append(member)
    seen_events: set[str] = set()
    event_ids = []
    for event_id in scene.event_ids:
        if event_id in seen_events:
            continue
        seen_events.add(event_id)
        event_ids.append(event_id)
    location_id = scene.location_id.strip() if scene.location_id else None
    return scene.model_copy(
        update={
            "setting": setting,
            "lines": lines,
            "cast": cast,
            "event_ids": event_ids,
            "location_id": location_id or None,
        }
    )


def _normalize_line(line: ScriptLine) -> ScriptLine:
    """Clean one line's text and clear fields that do not belong to its kind."""
    text = _clean_text(line.text)
    if line.kind == "dialogue":
        text = text.lstrip(_LEADING_DASHES).strip()
        return line.model_copy(
            update={"text": text, "actor_ids": [], "parenthetical": _unwrap(line.parenthetical)}
        )
    return line.model_copy(update={"text": text, "speaker_id": "", "parenthetical": ""})


def _sorted_scene(
    scene: ScriptSceneDraft,
    positions: dict[str, int],
) -> ScriptSceneDraft:
    """Sort one scene's event IDs by their position in the chapter, once they are known-good."""
    ordered = sorted(scene.event_ids, key=lambda event_id: positions[event_id])
    return scene.model_copy(update={"event_ids": ordered})


def _filled_location(
    scene: ScriptSceneDraft,
    event_location: dict[str, str],
) -> ScriptSceneDraft:
    """Fill a missing location from the scene's anchored events, when they agree."""
    if scene.location_id is not None:
        return scene
    declared = {
        event_location[event_id] for event_id in scene.event_ids if event_id in event_location
    }
    if len(declared) == 1:
        return scene.model_copy(update={"location_id": next(iter(declared))})
    return scene


def _validate_events_known(scenes: list[ScriptSceneDraft], known_event_ids: set[str]) -> None:
    """Require every cited event ID to exist in the plan."""
    offenders = []
    for index, scene in enumerate(scenes, 1):
        unknown = sorted(set(scene.event_ids) - known_event_ids)
        if unknown:
            offenders.append(f"scene {index} cites unknown event IDs: {', '.join(unknown)}")
    if offenders:
        allowed = ", ".join(sorted(known_event_ids))
        raise ValueError(f"{'; '.join(offenders)}; this act may stage only: {allowed}")


def _validate_events_in_chapter(
    scenes: list[ScriptSceneDraft],
    chapter_event_ids: set[str],
    plan: StoryPlan,
) -> None:
    """Require every cited event to belong to the chapter this act stages."""
    by_id = {event.id: event for event in plan.events}
    offenders = []
    for index, scene in enumerate(scenes, 1):
        foreign = [event_id for event_id in scene.event_ids if event_id not in chapter_event_ids]
        for event_id in foreign:
            foreign_chapter = by_id[event_id].chapter_id
            offenders.append(
                f"scene {index} stages event {event_id}, which belongs to chapter {foreign_chapter}"
            )
    if offenders:
        allowed = ", ".join(sorted(chapter_event_ids))
        raise ValueError(
            f"{'; '.join(offenders)}; this act may stage only the events of its own chapter: "
            f"{allowed}"
        )


def _validate_plan_order(
    scenes: list[ScriptSceneDraft],
    positions: dict[str, int],
    chapter_event_ids: set[str],
) -> None:
    """Require scenes to advance through the chapter's events in plan order.

    An event may continue into the next scene: only stepping backwards is rejected.
    """
    high_water_mark = -1
    for index, scene in enumerate(scenes, 1):
        scene_positions = [positions[event_id] for event_id in scene.event_ids]
        low, high = min(scene_positions), max(scene_positions)
        if low < high_water_mark:
            allowed = ", ".join(sorted(chapter_event_ids, key=positions.get))
            raise ValueError(
                f"scene {index} stages an event out of order; stage the events in plan order: "
                f"{allowed}"
            )
        high_water_mark = max(high_water_mark, high)


def _validate_full_coverage(scenes: list[ScriptSceneDraft], chapter_event_ids: set[str]) -> None:
    """Require every chapter event to be staged by at least one scene."""
    staged = {event_id for scene in scenes for event_id in scene.event_ids}
    missing = sorted(chapter_event_ids - staged)
    if missing:
        raise ValueError(
            f"no scene stages {', '.join(missing)}; every event of this chapter must be staged "
            "by at least one scene"
        )


def _validate_known_locations(scenes: list[ScriptSceneDraft], known_locations: set[str]) -> None:
    """Require every declared scene location to exist in the world."""
    offenders = []
    for index, scene in enumerate(scenes, 1):
        if scene.location_id is not None and scene.location_id not in known_locations:
            offenders.append(f"scene {index} is set in unknown location {scene.location_id}")
    if offenders:
        allowed = ", ".join(sorted(known_locations)) or "(none)"
        raise ValueError(f"{'; '.join(offenders)}; allowed location IDs: {allowed}")


def _validate_scene_location_agreement(
    scenes: list[ScriptSceneDraft],
    event_location: dict[str, str],
) -> None:
    """Require one scene's location to match every anchored event that declares one."""
    offenders = []
    for index, scene in enumerate(scenes, 1):
        declared = {
            event_location[event_id] for event_id in scene.event_ids if event_id in event_location
        }
        if len(declared) > 1:
            offenders.append(
                f"scene {index} stages events at different locations: {', '.join(sorted(declared))}"
            )
        elif declared and scene.location_id not in declared:
            expected = next(iter(declared))
            offenders.append(
                f"scene {index} is set in {scene.location_id}, but its events take place at "
                f"{expected}"
            )
    if offenders:
        raise ValueError("; ".join(offenders))


def _validate_cast_known(scenes: list[ScriptSceneDraft], known_characters: set[str]) -> None:
    """Require the cast of every scene to be known characters."""
    offenders = []
    for index, scene in enumerate(scenes, 1):
        unknown = sorted({member.character_id for member in scene.cast} - known_characters)
        if unknown:
            offenders.append(f"scene {index} casts unknown character IDs: {', '.join(unknown)}")
    if offenders:
        allowed = ", ".join(sorted(known_characters))
        raise ValueError(
            f"{'; '.join(offenders)}; allowed character IDs: {allowed}. A minor figure may appear "
            "inside a stage direction but cannot join the cast"
        )


def _validate_dialogue_speakers(scenes: list[ScriptSceneDraft]) -> None:
    """Require every dialogue line to name a speaker who is in that scene's cast."""
    missing = []
    foreign = []
    for scene_index, scene in enumerate(scenes, 1):
        cast_ids = {member.character_id for member in scene.cast}
        for line_index, line in enumerate(scene.lines, 1):
            if line.kind != "dialogue":
                continue
            if not line.speaker_id:
                missing.append(f"line {line_index} of scene {scene_index} has no speaker_id")
            elif line.speaker_id not in cast_ids:
                foreign.append(
                    f"line {line_index} of scene {scene_index} is spoken by {line.speaker_id}, "
                    f"who is not in that scene's cast: {', '.join(sorted(cast_ids)) or '(none)'}"
                )
    if missing:
        raise ValueError("; ".join(missing))
    if foreign:
        raise ValueError("; ".join(foreign))


def _validate_direction_lines(scenes: list[ScriptSceneDraft]) -> None:
    """Require every stage-direction actor to be in that scene's cast.

    A direction's speaker_id and parenthetical are cleared during normalization (see
    _normalize_line), so there is nothing left to reject on that front here.
    """
    foreign = []
    for scene_index, scene in enumerate(scenes, 1):
        cast_ids = {member.character_id for member in scene.cast}
        for line_index, line in enumerate(scene.lines, 1):
            if line.kind != "direction":
                continue
            unknown_actors = sorted(set(line.actor_ids) - cast_ids)
            if unknown_actors:
                foreign.append(
                    f"line {line_index} of scene {scene_index} names actor_ids "
                    f"{', '.join(unknown_actors)}, who are not in that scene's cast: "
                    f"{', '.join(sorted(cast_ids)) or '(none)'}"
                )
    if foreign:
        raise ValueError("; ".join(foreign))


def _validate_has_dialogue(scenes: list[ScriptSceneDraft]) -> None:
    """Require the act to stage at least one spoken line."""
    if not any(line.kind == "dialogue" for scene in scenes for line in scene.lines):
        raise ValueError(
            "the act has no dialogue line; let the characters speak the confrontations the "
            "events stage"
        )


def _observations(scenes: list[ScriptSceneDraft], chapter_events: list[PlotEvent]) -> list[str]:
    """Report non-blocking findings a valid act can still carry."""
    observations: list[str] = []
    staged_cast: dict[str, set[str]] = {}
    for scene in scenes:
        for event_id in scene.event_ids:
            staged_cast.setdefault(event_id, set()).update(
                member.character_id for member in scene.cast
            )
    for event in chapter_events:
        absent = sorted(set(event.character_ids) - staged_cast.get(event.id, set()))
        if absent:
            observations.append(
                f"{event.id} lists participants never cast in a scene staging it: "
                f"{', '.join(absent)}"
            )
    for index, scene in enumerate(scenes, 1):
        speaking = {line.speaker_id for line in scene.lines if line.kind == "dialogue"}
        acting = {
            actor for line in scene.lines if line.kind == "direction" for actor in line.actor_ids
        }
        idle = sorted({member.character_id for member in scene.cast} - speaking - acting)
        if idle:
            observations.append(f"scene {index} casts idle characters: {', '.join(idle)}")
    return observations


__all__ = [
    "act_anchor_index",
    "assemble_play",
    "materialize_act",
    "normalized_frame",
    "revision_issue",
]
