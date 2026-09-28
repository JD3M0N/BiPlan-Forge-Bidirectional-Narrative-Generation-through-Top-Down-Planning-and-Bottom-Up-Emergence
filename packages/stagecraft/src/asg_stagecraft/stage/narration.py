"""Who narrates, and what each chapter lets them see: decided before a word of prose.

Pure and deterministic, so the narration stage only has to call the model for chapters that
have something to tell. Two rules live here:

- A character someone asked for narrates, if the cast has them and they witnessed anything;
  otherwise the default narrator does, and the run says why.
- A chapter nobody on this point of view could see is not narrated at all. Sending an empty log
  to the narrator asked it to invent a chapter, which is the one thing it may never do.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

from ..formats import NarrativeVoice
from ..schemas import ChapterPlan, PlayScript, StoryPlan
from .names import resolve_character
from .schemas import ScenePerformance, StageTurn
from .voices import VOICES, narrator_character, visible_turns

NarratorSource = Literal["none", "requested", "protagonist", "most_turns"]


@dataclass(frozen=True)
class NarratorChoice:
    """The character a voice is told from, how they were chosen, and any fallback to report."""

    character_id: str
    source: NarratorSource
    warning: str = ""


@dataclass(frozen=True)
class ChapterView:
    """One chapter of the plan as the chosen point of view is able to see it."""

    chapter: ChapterPlan
    index: int
    scenes: list[ScenePerformance]
    visible: list[StageTurn]
    available: int


def scene_presence(play: PlayScript) -> dict[str, frozenset[str]]:
    """Map every scripted scene to the characters on stage in it."""
    return {
        scene.id: frozenset(member.character_id for member in scene.cast)
        for act in play.acts
        for scene in act.scenes
    }


def witnessed_anything(
    character_id: str,
    scenes: list[ScenePerformance],
    presence: dict[str, frozenset[str]],
) -> bool:
    """Say whether a character stood in any performed scene and perceived a turn of it."""
    return any(
        character_id in presence.get(scene.scene_id, frozenset({character_id}))
        and any(character_id in set(turn.witnesses) for turn in scene.turns)
        for scene in scenes
    )


def choose_narrator(
    voice: NarrativeVoice,
    scenes: list[ScenePerformance],
    *,
    requested: str,
    names: dict[str, str],
    protagonist: str,
    presence: dict[str, frozenset[str]],
) -> NarratorChoice:
    """Pick the character a voice is told from, falling back when the request cannot hold."""
    if not VOICES[voice].needs_narrator:
        return NarratorChoice("", "none")
    warning = ""
    if requested:
        chosen = resolve_character(requested, names)
        if chosen and witnessed_anything(chosen, scenes, presence):
            return NarratorChoice(chosen, "requested")
        warning = (
            f"[NARRATOR_FALLBACK] {names.get(chosen, chosen)} no presencio ninguna escena"
            if chosen
            else f"[NARRATOR_FALLBACK] Nadie del reparto responde al nombre {requested!r}"
        )
    if protagonist and witnessed_anything(protagonist, scenes, presence):
        default, source = protagonist, "protagonist"
    else:
        default, source = narrator_character(voice, scenes), "most_turns"
    if warning:
        warning = f"{warning}; narra {names.get(default, default)}."
    return NarratorChoice(default, source, warning)


def chapter_views(
    voice: NarrativeVoice,
    plan: StoryPlan,
    scenes: list[ScenePerformance],
    *,
    narrator: str,
    presence: dict[str, frozenset[str]],
) -> list[ChapterView]:
    """Split the performance by chapter and keep, for each, only the turns this voice sees."""
    by_chapter: dict[str, list[ScenePerformance]] = {}
    for scene in scenes:
        by_chapter.setdefault(scene.chapter_id, []).append(scene)
    views: list[ChapterView] = []
    for index, chapter in enumerate(plan.chapters, 1):
        chapter_scenes = by_chapter.get(chapter.id, [])
        visible = [
            turn
            for scene in chapter_scenes
            for turn in visible_turns(
                voice, scene, narrator=narrator, present=presence.get(scene.scene_id)
            )
        ]
        views.append(
            ChapterView(
                chapter=chapter,
                index=index,
                scenes=chapter_scenes,
                visible=visible,
                available=sum(len(scene.turns) for scene in chapter_scenes),
            )
        )
    return views


def narrated_chapter_ids(views: Collection[ChapterView]) -> list[str]:
    """Return, in plan order, the chapters that have at least one turn to narrate."""
    return [view.chapter.id for view in views if view.visible]
