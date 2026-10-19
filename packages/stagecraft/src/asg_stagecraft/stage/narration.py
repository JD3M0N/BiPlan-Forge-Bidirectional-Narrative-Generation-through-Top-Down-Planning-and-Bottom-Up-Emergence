"""Who narrates, and what each chapter lets them see: decided before a word of prose.

Pure and deterministic, so the narration stage only has to call the model for chapters that
have something to tell. Two rules live here:

- A character someone asked for narrates, if the cast has them and they witnessed anything;
  otherwise the default narrator does, and the run says why.
- A chapter nobody on this point of view could see is not narrated at all. Sending an empty log
  to the narrator asked it to invent a chapter, which is the one thing it may never do.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Literal

from ..formats import NarrativeVoice
from ..schemas import ChapterPlan, PlayScript, StoryPlan
from .names import resolve_character
from .schemas import ReportedLines, ScenePerformance, StageTurn
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
            f"[NARRATOR_FALLBACK] {names.get(chosen, chosen)} no presenció ninguna escena"
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


# How many words in a row a retelling may share with the line it retells before it counts as a
# copy. Four is a phrase ("no pienso soltar nada"); a name plus a verb is three.
COPIED_RUN = 4
# The narrator still reads one line in WHOLE_EVERY of a chapter's speech whole, and at least
# MIN_WHOLE. Key lines come from the beats that landed, so a forced beat has none: the 7.15.2
# finale had 12 lines and no key one, and would have reached the narrator as summary only.
# The lines the reporter marks to keep fill the gap, earliest first.
WHOLE_EVERY = 3
MIN_WHOLE = 2
_REPORT_WORD = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass
class AcceptedReports:
    """The retellings the narrator may read, and the ones the code turned away and why."""

    reports: dict[str, str] = field(default_factory=dict)
    rejected: dict[str, str] = field(default_factory=dict)
    kept: list[str] = field(default_factory=list)
    retried: list[str] = field(default_factory=list)

    def as_record(self) -> dict:
        """The decision as stored next to the chapter on disk."""
        return {
            "kept": self.kept,
            "accepted": self.reports,
            "rejected": self.rejected,
            "retried": self.retried,
        }

    def merge(self, retry: AcceptedReports) -> None:
        """Take the retellings a second request got, keeping this one's whole lines."""
        self.reports.update(retry.reports)
        for turn_id in retry.reports:
            self.rejected.pop(turn_id, None)
        self.rejected.update(
            {key: why for key, why in retry.rejected.items() if key not in self.reports}
        )


def whole_lines_wanted(turns: list[StageTurn], key_ids: Collection[str]) -> int:
    """Say how many more lines a chapter should keep whole beyond its key ones."""
    spoken = [turn for turn in turns if turn.kind == "actor" and turn.speech]
    target = max(MIN_WHOLE, -(-len(spoken) // WHOLE_EVERY))
    return max(0, min(len(spoken), target) - sum(turn.id in key_ids for turn in spoken))


def lines_to_report(
    turns: list[StageTurn], key_ids: Collection[str], names: dict[str, str]
) -> list[dict]:
    """List the lines of speech a chapter does not turn on, as the reporter reads them.

    Each line gets a short id (L1, L2...). Given turn ids, the model renumbered the second
    scene's lines as the first scene's and lost 12 of 16 retellings.
    """
    spoken = [
        turn for turn in turns if turn.kind == "actor" and turn.speech and turn.id not in key_ids
    ]
    return [
        {
            "id": f"L{number}",
            "turn_id": turn.id,
            "speaker": names.get(turn.actor_id, turn.actor_id),
            "to": [names.get(item, item) for item in turn.addressed_to],
            "whispered": turn.visibility == "whisper",
            "speech": turn.speech,
        }
        for number, turn in enumerate(spoken, 1)
    ]


def reporter_view(line: dict) -> dict:
    """The part of a listed line the reporter reads: everything but the turn id."""
    return {key: value for key, value in line.items() if key != "turn_id"}


def accept_reports(lines: list[dict], drafted: ReportedLines, keep: int = 0) -> AcceptedReports:
    """Keep one retelling per requested line, turning away any that copies the line itself.

    Up to ``keep`` of the lines the reporter ranked as memorable stay whole, in its order.
    """
    by_id = {line["id"]: line for line in lines}
    accepted = AcceptedReports()
    ranked = [item for item in dict.fromkeys(drafted.memorable) if item in by_id]
    accepted.kept = [by_id[item]["turn_id"] for item in ranked[:keep]]
    for item in drafted.lines:
        line = by_id.get(item.id)
        report = " ".join(item.report.split())
        if line is None or line["turn_id"] in accepted.reports:
            accepted.rejected[item.id] = "unknown or repeated line"
        elif shares_run(report, line["speech"]):
            accepted.rejected[line["turn_id"]] = "copies the line"
        else:
            accepted.reports[line["turn_id"]] = report
    return accepted


def unreported(lines: list[dict], accepted: AcceptedReports) -> list[dict]:
    """List the lines with no accepted retelling that are not kept whole either (7.19).

    In the 7.18 islands run the reporter retold four of a chapter's lines, all from its first
    scene; the rest reached the narrator whole, and the chapter transcribed them.
    """
    done = set(accepted.reports) | set(accepted.kept)
    return [line for line in lines if line["turn_id"] not in done]


def shares_run(report: str, speech: str) -> bool:
    """Say whether a retelling repeats COPIED_RUN or more words of the line in a row."""
    said = [word.casefold() for word in _REPORT_WORD.findall(speech)]
    runs = {tuple(said[index : index + COPIED_RUN]) for index in range(len(said) - COPIED_RUN + 1)}
    told = [word.casefold() for word in _REPORT_WORD.findall(report)]
    return any(
        tuple(told[index : index + COPIED_RUN]) in runs
        for index in range(len(told) - COPIED_RUN + 1)
    )
