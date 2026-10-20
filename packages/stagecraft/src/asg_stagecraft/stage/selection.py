"""Choose the moments a chapter is told through, before a word of prose (7.17).

The narration_method=selected arm. Flash-Lite copies what it is handed: the whole log came back
transcribed (7.13 to 7.15.2) and the lines retold in indirect style came back as minutes (7.16).
So the narrator no longer gets the log. A first call groups the log into moments and decides,
for each, whether it is played as scene or passes in one sentence; the narrator then writes from
those moments, the places and the cast. In2Writing (2025) and BookWorld (ACL 2025) narrate a
simulation the same way: from a scene outline, with the log as the evidence behind it.

The code keeps the contract the narrator had: nothing it is handed comes from outside the log,
every world event and every line a beat landed on is told, and no more than half of a chapter is
played out line by line. A summary that copies its own lines is turned away like a retelling.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field

from ..schemas import PlayScript, ScriptScene, WorldArtifact
from .narration import shares_run
from .perception import stage_direction
from .render import scene_log
from .schemas import CastBible, ChapterSelection, StageTurn

# No more than this share of a chapter's lines is played out line by line; the rest passes in
# a sentence or is cut. Key lines and world events may always be played.
SCENE_SHARE = 0.5
MIN_SCENE_LINES = 2


@dataclass
class Moment:
    """A run of consecutive lines told one way: played out, or passed in one sentence."""

    turn_ids: list[str]
    treatment: str
    gist: str
    bridge: str = ""


@dataclass
class Selection:
    """The moments a chapter is told through, and what the code had to correct."""

    moments: list[Moment] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)

    def as_record(self) -> dict:
        """The selection as stored next to the chapter on disk."""
        return {
            "moments": [
                {
                    "turn_ids": moment.turn_ids,
                    "treatment": moment.treatment,
                    "gist": moment.gist,
                    "bridge": moment.bridge,
                }
                for moment in self.moments
            ],
            "repairs": self.repairs,
        }


def selection_lines(
    turns: list[StageTurn], names: dict[str, str], key_ids: Collection[str]
) -> list[dict]:
    """List every visible turn of a chapter as the selector reads it, with short ids."""
    scenes: dict[str, str] = {}
    lines = []
    for number, turn in enumerate(turns, 1):
        scene = scenes.setdefault(turn.scene_id, f"S{len(scenes) + 1}")
        line: dict = {"id": f"L{number}", "turn_id": turn.id, "scene": scene}
        if turn.kind == "world":
            line["world"] = turn.action
        else:
            speaker = names.get(turn.actor_id, turn.actor_id)
            line["who"] = speaker
            if turn.action:
                line["does"] = stage_direction(speaker, turn.action, names)
            if turn.speech:
                line["says"] = turn.speech
            if turn.thought:
                line["thinks"] = turn.thought
        if turn.kind == "world" or turn.id in key_ids:
            line["key"] = True
        lines.append(line)
    return lines


def selector_view(lines: list[dict]) -> list[dict]:
    """The part of each line the selector reads: everything but the turn id."""
    return [{key: value for key, value in line.items() if key != "turn_id"} for line in lines]


def accept_selection(lines: list[dict], drafted: ChapterSelection) -> Selection:
    """Turn a drafted selection into one that keeps the narrator's contract, or raise.

    Normalizes more than it rejects: an unknown or repeated id is dropped, a key line left out
    comes back as a scene of its own, moments are put back in the order of the log, and played
    lines over the share pass to summary, the latest first. Only a selection with nothing left
    is a failure, and the chapter is then narrated the 7.16 way.
    """
    by_id = {line["id"]: line for line in lines}
    order = {line["id"]: index for index, line in enumerate(lines)}
    used: set[str] = set()
    selection = Selection()
    for drafted_moment in drafted.moments:
        ids = [item for item in dict.fromkeys(drafted_moment.lines) if item in by_id]
        ids = [item for item in ids if item not in used]
        if not ids:
            selection.repairs.append("a moment with no new line was dropped")
            continue
        used.update(ids)
        keyed = any(by_id[item].get("key") for item in ids)
        gist = " ".join(drafted_moment.gist.split())
        treatment = drafted_moment.treatment
        if treatment == "summary" and _copies(gist, ids, by_id):
            treatment = "scene" if keyed else "cut"
            selection.repairs.append(f"the summary of {ids[0]} copied its lines")
        if treatment == "cut":
            continue
        ordered = sorted(ids, key=order.__getitem__)
        selection.moments.append(
            Moment(ordered, treatment, gist, " ".join(drafted_moment.bridge.split()))
        )
    for line in lines:
        if line.get("key") and line["id"] not in used:
            selection.moments.append(Moment([line["id"]], "scene", ""))
            selection.repairs.append(f"{line['id']} is key and was restored")
    if not selection.moments:
        raise ValueError("the selection kept no moment of the chapter")
    selection.moments.sort(key=lambda moment: order[moment.turn_ids[0]])
    _cap_scene(selection, lines, by_id)
    for moment in selection.moments:
        moment.turn_ids = [by_id[item]["turn_id"] for item in moment.turn_ids]
    return selection


def selection_material(
    selection: Selection,
    turns: list[StageTurn],
    names: dict[str, str],
    *,
    places: list[str],
    cast: list[str],
    previous: str,
) -> str:
    """Render what the narrator writes from: places, cast, the last paragraph and the moments."""
    by_id = {turn.id: turn for turn in turns}
    parts = []
    if places:
        parts.append("LUGARES:\n" + "\n".join(f"- {place}" for place in places))
    if cast:
        parts.append("REPARTO:\n" + "\n".join(f"- {member}" for member in cast))
    if previous:
        parts.append(f"FINAL DEL CAPÍTULO ANTERIOR:\n{previous}")
    moments = []
    for number, moment in enumerate(selection.moments, 1):
        label = "ESCENA" if moment.treatment == "scene" else "RESUMEN"
        lines = [f"{number}. [{label}]"]
        if moment.bridge:
            lines.append(f"Paso a esta escena: {moment.bridge}")
        if moment.gist:
            lines.append(f"Qué pasa: {moment.gist}")
        if moment.treatment == "scene":
            played = [by_id[item] for item in moment.turn_ids if item in by_id]
            lines.append(scene_log(played, names, thoughts=True, short_names=True))
        moments.append("\n".join(lines))
    parts.append("MOMENTOS:\n" + "\n\n".join(moments))
    return "\n\n".join(parts)


def _copies(gist: str, ids: list[str], by_id: dict[str, dict]) -> bool:
    """Say whether a summary is empty or repeats a run of words of one of its lines."""
    if not gist:
        return True
    return any(shares_run(gist, by_id[item].get("says", "")) for item in ids)


def _cap_scene(selection: Selection, lines: list[dict], by_id: dict[str, dict]) -> None:
    """Pass played moments to summary, the latest first, until the share holds."""
    cap = max(MIN_SCENE_LINES, int(SCENE_SHARE * len(lines)))
    played = sum(
        len(moment.turn_ids) for moment in selection.moments if moment.treatment == "scene"
    )
    for moment in reversed(selection.moments):
        if played <= cap:
            return
        keyed = any(by_id[item].get("key") for item in moment.turn_ids)
        if moment.treatment == "scene" and moment.gist and not keyed:
            moment.treatment = "summary"
            played -= len(moment.turn_ids)
            selection.repairs.append(f"{moment.turn_ids[0]} passed to summary")


def script_scenes(play: PlayScript) -> dict[str, ScriptScene]:
    """Index the scenes of a script by their id."""
    return {scene.id: scene for act in play.acts for scene in act.scenes}


def _scene_order(turns: list[StageTurn]) -> list[str]:
    """Return the scenes of a chapter in the order its visible turns first reach them."""
    return list(dict.fromkeys(turn.scene_id for turn in turns))


def scene_settings(turns: list[StageTurn], scenes: dict[str, ScriptScene]) -> dict[str, str]:
    """Label each scene of a chapter as the selector reads it (S1...), with its setting."""
    return {
        f"S{number}": scenes[scene_id].setting if scene_id in scenes else ""
        for number, scene_id in enumerate(_scene_order(turns), 1)
    }


def chapter_places(
    turns: list[StageTurn], scenes: dict[str, ScriptScene], world: WorldArtifact | None
) -> list[str]:
    """Describe the places a chapter happens in, from the script, or by the world's name.

    The script's setting comes first (7.20): it is written in the fiction's language, while the
    world's descriptions are planned in English, so the 7.17 selection could read "The elevated
    residential platforms..." in a Spanish chapter.
    """
    locations = {location.id: location for location in (world.locations if world else [])}
    places: list[str] = []
    for scene_id in _scene_order(turns):
        scene = scenes.get(scene_id)
        if scene is None:
            continue
        location = locations.get(scene.location_id or "")
        place = scene.setting or (location.name if location else "")
        if place and place not in places:
            places.append(place)
    return places


def on_stage(turns: list[StageTurn], scenes: dict[str, ScriptScene]) -> list[str]:
    """Return everyone on stage in the scenes a chapter's turns reach, in order of entrance."""
    present: list[str] = []
    for scene_id in _scene_order(turns):
        for member in scenes[scene_id].cast if scene_id in scenes else []:
            if member.character_id not in present:
                present.append(member.character_id)
    return present


def chapter_cast(
    turns: list[StageTurn],
    scenes: dict[str, ScriptScene],
    names: dict[str, str],
    bible: CastBible | None,
    *,
    introduced: Collection[str] = (),
) -> list[str]:
    """Name everyone on stage in a chapter, with what anyone can see of them (SIM-5).

    ``introduced`` leaves out whoever an earlier chapter already brought on (7.20): handed the
    whole cast again, the 7.19 islands narrator described Nilo by his looks in chapter 3.
    """
    faces = {item.character_id: item.public_face for item in (bible.dossiers if bible else [])}
    return [
        f"{names.get(item, item)}: {faces[item]}" if faces.get(item) else names.get(item, item)
        for item in on_stage(turns, scenes)
        if item not in introduced
    ]


def last_paragraph(body: str) -> str:
    """Return the last paragraph of a chapter, where the next one picks up."""
    blocks = [block.strip() for block in body.strip().split("\n\n") if block.strip()]
    return blocks[-1] if blocks else ""
