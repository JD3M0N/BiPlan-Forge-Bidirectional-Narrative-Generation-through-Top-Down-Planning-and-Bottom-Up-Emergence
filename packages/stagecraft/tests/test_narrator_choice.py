"""7.3: choosing who narrates, and leaving out what that point of view never saw."""

import pytest
from asg_stagecraft.agents.narrator import _VOICE_CLAUSES, narrator_clause, tone_clause
from asg_stagecraft.formats import VOICE_CHOICES, NarrativeVoice
from asg_stagecraft.planning.graph import materialize_plan
from asg_stagecraft.stage import voices
from asg_stagecraft.stage.names import resolve_character
from asg_stagecraft.stage.narration import (
    chapter_views,
    choose_narrator,
    narrated_chapter_ids,
    witnessed_anything,
)
from asg_stagecraft.stage.schemas import BeatRecord, ScenePerformance, StageTurn
from asg_stagecraft.writing.assembly import narrated_plan
from asg_stagecraft.writing.audit import story_metrics
from test_generator_v5 import make_characters, make_request, make_world, valid_plan

NAMES = {"ana": "Ana Vela", "luis": "Luis Soto", "cora": "Cora Soto"}


def turn(scene_id, number, actor_id, *, witnesses, thought=""):
    return StageTurn(
        id=f"{scene_id}-t{number:03d}",
        scene_id=scene_id,
        number=number,
        actor_id=actor_id,
        beat_index=0,
        beat_event_id="event-1",
        witnesses=list(witnesses),
        speech=f"Linea {number} de {actor_id}.",
        thought=thought,
        tactic="confront",
    )


def scene(scene_id, chapter_id, turns):
    return ScenePerformance(
        scene_id=scene_id,
        number=int(scene_id.rsplit("-", 1)[1]),
        chapter_id=chapter_id,
        turns=turns,
        beats=[BeatRecord(event_id="event-1", index=0, achieved=True)],
    )


def two_chapters(*, shared_memory=False):
    """Chapter one has Ana and Luis on stage; chapter two only Luis and Cora."""
    everyone = list(NAMES)
    first = scene(
        "chapter-1-scene-1",
        "chapter-1",
        [
            turn("chapter-1-scene-1", 1, "ana", witnesses=["ana", "luis"], thought="Miente."),
            turn("chapter-1-scene-1", 2, "luis", witnesses=["ana", "luis"], thought="Lo sabe."),
        ],
    )
    second = scene(
        "chapter-2-scene-2",
        "chapter-2",
        [
            turn(
                "chapter-2-scene-2",
                1,
                "luis",
                witnesses=everyone if shared_memory else ["luis", "cora"],
            ),
            turn(
                "chapter-2-scene-2",
                2,
                "cora",
                witnesses=everyone if shared_memory else ["luis", "cora"],
            ),
        ],
    )
    presence = {
        "chapter-1-scene-1": frozenset({"ana", "luis"}),
        "chapter-2-scene-2": frozenset({"luis", "cora"}),
    }
    return [first, second], presence


def plan():
    return materialize_plan(valid_plan(), make_world(), make_characters())


# -- resolving a typed name ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("Ana Vela", "ana"),
        ("ana", "ana"),
        ("ÁNA", "ana"),
        ("Vela", "ana"),
        ("luis", "luis"),
        ("Cora", "cora"),
        ("Soto", ""),  # Luis Soto and Cora Soto: ambiguous resolves to nobody
        ("Zoe", ""),
        ("  ", ""),
        ("de", ""),  # too short to identify anyone on its own
    ],
)
def test_a_typed_name_resolves_to_one_character_or_to_nobody(typed, expected) -> None:
    assert resolve_character(typed, NAMES) == expected


# -- choosing the narrator ----------------------------------------------------------------


def test_the_requested_character_narrates_when_they_saw_something() -> None:
    scenes, presence = two_chapters()
    choice = choose_narrator(
        NarrativeVoice.LIMITED,
        scenes,
        requested="ana",
        names=NAMES,
        protagonist="luis",
        presence=presence,
    )
    assert (choice.character_id, choice.source, choice.warning) == ("ana", "requested", "")


def test_an_unknown_name_falls_back_and_says_so() -> None:
    scenes, presence = two_chapters()
    choice = choose_narrator(
        NarrativeVoice.FIRST_PERSON,
        scenes,
        requested="Zoe",
        names=NAMES,
        protagonist="luis",
        presence=presence,
    )
    assert (choice.character_id, choice.source) == ("luis", "protagonist")
    assert choice.warning.startswith("[NARRATOR_FALLBACK]")
    assert "Zoe" in choice.warning and "Luis Soto" in choice.warning


def test_a_character_who_witnessed_nothing_cannot_narrate() -> None:
    scenes, presence = two_chapters()
    silent = {**NAMES, "eva": "Eva Ruiz"}
    choice = choose_narrator(
        NarrativeVoice.LIMITED,
        scenes,
        requested="Eva",
        names=silent,
        protagonist="",
        presence=presence,
    )
    assert choice.source == "most_turns"
    assert "Eva Ruiz no presencio ninguna escena" in choice.warning


def test_a_voice_told_from_nobody_needs_no_narrator() -> None:
    scenes, presence = two_chapters()
    for voice in (NarrativeVoice.OMNISCIENT, NarrativeVoice.FOCALIZED):
        choice = choose_narrator(
            voice, scenes, requested="", names=NAMES, protagonist="ana", presence=presence
        )
        assert (choice.character_id, choice.source, choice.warning) == ("", "none", "")


# -- what each chapter lets the narrator see ------------------------------------------------


def test_a_chapter_the_narrator_never_stood_in_is_left_out() -> None:
    scenes, presence = two_chapters()
    views = chapter_views(NarrativeVoice.LIMITED, plan(), scenes, narrator="ana", presence=presence)
    assert [len(view.visible) for view in views] == [2, 0]
    assert [view.available for view in views] == [2, 2]
    assert narrated_chapter_ids(views) == ["chapter-1"]
    # Only Ana's own thought survives in the chapter she narrates.
    assert [item.thought for item in views[0].visible] == ["Miente.", ""]


def test_shared_memory_never_lets_the_narrator_see_a_scene_they_were_not_in() -> None:
    scenes, presence = two_chapters(shared_memory=True)
    # Under shared memory every public turn lists the whole cast as its witnesses...
    assert "ana" in scenes[1].turns[0].witnesses
    # ...but a narrator told from Ana still sees nothing of a scene she was not in.
    views = chapter_views(
        NarrativeVoice.FIRST_PERSON, plan(), scenes, narrator="ana", presence=presence
    )
    assert narrated_chapter_ids(views) == ["chapter-1"]
    assert not witnessed_anything("ana", scenes[1:], presence)


def test_voices_told_from_nobody_see_every_chapter() -> None:
    scenes, presence = two_chapters()
    for voice in (NarrativeVoice.OMNISCIENT, NarrativeVoice.FOCALIZED):
        views = chapter_views(voice, plan(), scenes, narrator="", presence=presence)
        assert narrated_chapter_ids(views) == ["chapter-1", "chapter-2"]


def test_the_narrated_plan_drops_the_events_of_left_out_chapters_too() -> None:
    full = plan()
    narrated = narrated_plan(full, ["chapter-1"])
    assert [chapter.id for chapter in narrated.chapters] == ["chapter-1"]
    assert {event.chapter_id for event in narrated.events} == {"chapter-1"}
    story = "# Titulo\n\n## El archivo\n\nAna cerro la puerta y no dijo nada."
    metrics = story_metrics(make_request(), narrated, story)
    assert metrics.chapters == 1
    assert metrics.chapter_bodies_recovered is True


# -- every voice is complete ----------------------------------------------------------------


def test_every_voice_has_a_label_a_strategy_and_a_clause() -> None:
    labelled = {item.voice for item in VOICE_CHOICES}
    assert labelled == set(NarrativeVoice)
    assert set(voices.VOICES) == set(NarrativeVoice)
    assert set(_VOICE_CLAUSES) == set(NarrativeVoice)
    for item in VOICE_CHOICES:
        assert item.takes_character == voices.VOICES[item.voice].needs_narrator, item.voice


def test_the_narrator_clause_keeps_first_person_unchanged() -> None:
    assert narrator_clause(NarrativeVoice.FIRST_PERSON, "Ana") == " You are narrating as Ana."
    assert narrator_clause(NarrativeVoice.LIMITED, "Ana") == (
        " The point-of-view character is Ana."
    )
    assert narrator_clause(NarrativeVoice.OMNISCIENT, "Ana") == ""
    assert narrator_clause(NarrativeVoice.FIRST_PERSON, "") == ""


def test_a_tone_is_carried_only_when_there_is_one() -> None:
    assert tone_clause("") == ""
    assert tone_clause("   ") == ""
    clause = tone_clause("como un guerrero samurái, con tono medieval")
    assert "como un guerrero samurái, con tono medieval" in clause
    assert "never the events" in clause
