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
# A stage direction is written in the present, so a sentence that opens on its first words has
# copied its tense too. Measured on the 7.13 navigators run: the chapter told in the present
# reused 15 directions this way, every other chapter of that run and of 7.12 at most one.
DIRECTION_WORDS = 4
# The narrator still reads one line in WHOLE_EVERY of a chapter's speech whole, and at least
# MIN_WHOLE. Key lines come from the beats that landed, so a forced beat has none: the 7.15.2
# finale had 12 lines and no key one, and would have reached the narrator as summary only.
# The lines the reporter marks to keep fill the gap, earliest first.
WHOLE_EVERY = 3
MIN_WHOLE = 2
_REPORT_WORD = re.compile(r"[^\W_]+", re.UNICODE)

# The short id prefix each kind of item reaches the reporter with.
_PREFIX: dict[str, str] = {
    "setting": "S",
    "speech": "L",
    "gesture": "G",
    "thought": "T",
    "event": "E",
}


@dataclass
class AcceptedReports:
    """The retellings the narrator may read, and the ones the code turned away and why.

    Since 7.20 the reporter retells every gesture, thought and world event as well as the lines
    nobody turns on: a direction reached the narrator in the present, and in the 7.19 islands run
    the narrator pasted it whole, tense and all, into chapters told in the past.
    """

    reports: dict[str, str] = field(default_factory=dict)
    gestures: dict[str, str] = field(default_factory=dict)
    thoughts: dict[str, str] = field(default_factory=dict)
    settings: dict[str, str] = field(default_factory=dict)
    rejected: dict[str, str] = field(default_factory=dict)
    kept: list[str] = field(default_factory=list)
    retried: list[str] = field(default_factory=list)
    done: set[str] = field(default_factory=set)

    def bucket(self, kind: str) -> dict[str, str]:
        """Return where the retellings of one kind of item are kept, by turn or scene id."""
        buckets = {"speech": self.reports, "thought": self.thoughts, "setting": self.settings}
        return buckets.get(kind, self.gestures)

    def as_record(self) -> dict:
        """The decision as stored next to the chapter on disk."""
        return {
            "kept": self.kept,
            "accepted": self.reports,
            "gestures": self.gestures,
            "thoughts": self.thoughts,
            "settings": self.settings,
            "rejected": self.rejected,
            "retried": self.retried,
        }

    def merge(self, retry: AcceptedReports) -> None:
        """Take the retellings a second request got, keeping this one's whole lines."""
        for kind in ("speech", "gesture", "thought", "setting"):
            self.bucket(kind).update(retry.bucket(kind))
        self.done |= retry.done
        self.rejected = {key: why for key, why in self.rejected.items() if key not in retry.done}
        self.rejected.update(retry.rejected)


def whole_lines_wanted(turns: list[StageTurn], key_ids: Collection[str]) -> int:
    """Say how many more lines a chapter should keep whole beyond its key ones."""
    spoken = [turn for turn in turns if turn.kind == "actor" and turn.speech]
    target = max(MIN_WHOLE, -(-len(spoken) // WHOLE_EVERY))
    return max(0, min(len(spoken), target) - sum(turn.id in key_ids for turn in spoken))


def lines_to_report(
    turns: list[StageTurn],
    key_ids: Collection[str],
    names: dict[str, str],
    *,
    settings: dict[str, str] | None = None,
) -> list[dict]:
    """List what the reporter retells: lines nobody turns on, every gesture and world event.

    Each item gets a short id by kind (L1, G1, T1, E1...). Given turn ids, the model renumbered
    the second scene's lines as the first scene's and lost 12 of 16 retellings. A key line stays
    whole; its gesture is retold all the same, since a direction is never prose. Only a key
    turn's thought is retold: handed all eleven of a chapter's thoughts as narration, the first
    7.20 replay closed nearly every line with "Temia que...". ``settings`` are the scenes'
    settings, by scene id: written in the present, they were pasted as the chapter's opening.
    """
    counts = dict.fromkeys(_PREFIX, 0)
    items: list[dict] = []
    for scene_id, setting in (settings or {}).items():
        if setting:
            counts["setting"] += 1
            items.append(
                {
                    "id": f"S{counts['setting']}",
                    "turn_id": scene_id,
                    "kind": "setting",
                    "speaker": "",
                    "text": setting,
                }
            )

    def add(turn: StageTurn, kind: str, text: str, **extra) -> None:
        """Append one item of the given kind for a turn."""
        counts[kind] += 1
        speaker = names.get(turn.actor_id, turn.actor_id) if kind != "event" else ""
        items.append(
            {
                "id": f"{_PREFIX[kind]}{counts[kind]}",
                "turn_id": turn.id,
                "kind": kind,
                "speaker": speaker,
                **extra,
                "text": text,
            }
        )

    for turn in turns:
        if turn.kind == "world":
            if turn.action:
                add(turn, "event", turn.action)
            continue
        if turn.kind != "actor":
            continue
        if turn.action:
            add(turn, "gesture", turn.action)
        if turn.speech and turn.id not in key_ids:
            add(
                turn,
                "speech",
                turn.speech,
                to=[names.get(item, item) for item in turn.addressed_to],
                whispered=turn.visibility == "whisper",
            )
        if turn.thought and turn.id in key_ids:
            add(turn, "thought", turn.thought)
    return items


def reporter_view(line: dict) -> dict:
    """The part of a listed line the reporter reads: everything but the turn id."""
    return {key: value for key, value in line.items() if key != "turn_id"}


def accept_reports(lines: list[dict], drafted: ReportedLines, keep: int = 0) -> AcceptedReports:
    """Keep one retelling per requested item, turning away any that copies what it retells.

    Up to ``keep`` of the lines of speech the reporter ranked as memorable stay whole, in its
    order.
    """
    by_id = {line["id"]: line for line in lines}
    accepted = AcceptedReports()
    ranked = [
        item
        for item in dict.fromkeys(drafted.memorable)
        if item in by_id and by_id[item]["kind"] == "speech"
    ]
    accepted.kept = [by_id[item]["turn_id"] for item in ranked[:keep]]
    for item in drafted.lines:
        line = by_id.get(item.id)
        report = " ".join(item.report.split())
        if line is None or item.id in accepted.done:
            accepted.rejected[item.id] = "unknown or repeated line"
        elif copies_source(report, line["text"], line["kind"]):
            accepted.rejected[item.id] = "copies the line"
        else:
            accepted.bucket(line["kind"])[line["turn_id"]] = report
            accepted.done.add(item.id)
    return accepted


def copies_source(report: str, text: str, kind: str) -> bool:
    """Say whether a retelling copies its source: a phrase of a line, a direction's opening."""
    if kind in ("gesture", "event", "setting"):
        return opens_with_direction(report, text)
    return shares_run(report, text)


def opens_with_direction(prose: str, direction: str) -> bool:
    """Say whether a text contains the first DIRECTION_WORDS words of a stage direction."""
    words = [word.casefold() for word in _REPORT_WORD.findall(direction)][:DIRECTION_WORDS]
    if len(words) < DIRECTION_WORDS:
        return False
    told = " ".join(word.casefold() for word in _REPORT_WORD.findall(prose))
    return f" {' '.join(words)} " in f" {told} "


def unreported(lines: list[dict], accepted: AcceptedReports) -> list[dict]:
    """List the items with no accepted retelling that are not kept whole either (7.19).

    In the 7.18 islands run the reporter retold four of a chapter's lines, all from its first
    scene; the rest reached the narrator whole, and the chapter transcribed them.
    """
    return [
        line
        for line in lines
        if line["id"] not in accepted.done
        and not (line["kind"] == "speech" and line["turn_id"] in accepted.kept)
    ]


def shares_run(report: str, speech: str, run: int = COPIED_RUN) -> bool:
    """Say whether a retelling repeats ``run`` or more words of the line in a row."""
    said = [word.casefold() for word in _REPORT_WORD.findall(speech)]
    runs = {tuple(said[index : index + run]) for index in range(len(said) - run + 1)}
    told = [word.casefold() for word in _REPORT_WORD.findall(report)]
    return any(tuple(told[index : index + run]) in runs for index in range(len(told) - run + 1))
