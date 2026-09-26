import pytest
from asg_stagecraft.schemas import (
    ActScriptDraft,
    ChapterPlan,
    CharacterProfile,
    CharactersArtifact,
    Location,
    PlotEvent,
    RevisionNote,
    SceneCastMember,
    ScriptLine,
    ScriptSceneDraft,
    StoryPlan,
    WorldArtifact,
)
from asg_stagecraft.script.validation import act_anchor_index, materialize_act, revision_issue


def make_chapter() -> ChapterPlan:
    return ChapterPlan(
        id="chapter-1",
        order=1,
        title="The Archive",
        summary="Ana confronts Luis over the missing ledger.",
        dramatic_goal="Force a confession",
        opening_state="Ana suspects Luis",
        turning_point="Luis admits the theft",
        closing_state="Ana holds the evidence",
    )


def make_event(identifier: str, order: int, character_ids: list[str]) -> PlotEvent:
    return PlotEvent(
        id=identifier,
        order=order,
        chapter_id="chapter-1",
        title=identifier,
        description=f"Description for {identifier}",
        purpose="Advance the confrontation",
        dramatic_function="Escalate the conflict",
        conflict="Ana suspects Luis",
        outcome="The truth surfaces",
        character_ids=character_ids,
        location_id="archive",
        effects=["The truth is known"],
    )


def make_plan() -> StoryPlan:
    events = [make_event("event-1", 1, ["ana"]), make_event("event-2", 2, ["ana", "luis"])]
    return StoryPlan(
        logline="Ana confronts Luis",
        theme="Trust and betrayal",
        ending="Luis confesses",
        narrative_structure="Compact",
        dramatic_question="Will Luis confess?",
        stakes="Their partnership",
        chapters=[make_chapter()],
        events=events,
        dependencies=[],
        topological_order=["event-1", "event-2"],
    )


def make_world() -> WorldArtifact:
    return WorldArtifact(
        setting="A coastal archive",
        time_period="Present",
        rules=["The archive closes at dusk"],
        locations=[Location(id="archive", name="Archive", description="An old archive")],
        atmosphere="Tense",
    )


def make_characters() -> CharactersArtifact:
    return CharactersArtifact(
        characters=[
            CharacterProfile(
                id="ana",
                name="Ana",
                role="protagonist",
                goal="Uncover the truth",
                motivation="Protect the archive",
                conflict="Trusts Luis less each day",
                arc="Learns to confront directly",
                voice="Precise",
            ),
            CharacterProfile(
                id="luis",
                name="Luis",
                role="antagonist",
                goal="Hide the theft",
                motivation="Avoid disgrace",
                conflict="Cannot keep lying",
                arc="Is forced into honesty",
                voice="Evasive",
            ),
        ]
    )


def dialogue(speaker: str, text: str = "Nadie mas lo sabe.") -> ScriptLine:
    return ScriptLine(kind="dialogue", speaker_id=speaker, text=text)


def direction(actor_ids: list[str], text: str = "Cierra la puerta.") -> ScriptLine:
    return ScriptLine(kind="direction", actor_ids=actor_ids, text=text)


def valid_draft() -> ActScriptDraft:
    scene_one = ScriptSceneDraft(
        event_ids=["event-1"],
        location_id="archive",
        setting="El archivo al anochecer.",
        cast=[SceneCastMember(character_id="ana", objective="Find proof Luis lied")],
        lines=[direction(["ana"]), dialogue("ana")],
    )
    scene_two = ScriptSceneDraft(
        event_ids=["event-2"],
        location_id="archive",
        setting="Luis entra sin avisar.",
        cast=[
            SceneCastMember(character_id="ana", objective="Force a confession"),
            SceneCastMember(character_id="luis", objective="Deny everything"),
        ],
        lines=[direction(["luis"]), dialogue("luis", "Yo no fui.")],
    )
    return ActScriptDraft(scenes=[scene_one, scene_two])


def context():
    return {
        "chapter": make_chapter(),
        "number": 1,
        "plan": make_plan(),
        "world": make_world(),
        "characters": make_characters(),
    }


def test_valid_act_mints_scene_ids_and_numbers() -> None:
    act = materialize_act(valid_draft(), **context())
    assert [scene.id for scene in act.scenes] == ["chapter-1-scene-1", "chapter-1-scene-2"]
    assert [scene.number for scene in act.scenes] == [1, 2]
    assert act.chapter_id == "chapter-1"


def test_normalization_strips_wrapping_parens_and_heading_markers() -> None:
    draft = valid_draft()
    draft.scenes[0].setting = "## (El archivo al anochecer.)"
    draft.scenes[0].lines[1].text = "—Nadie mas lo sabe."
    act = materialize_act(draft, **context())
    assert act.scenes[0].setting == "El archivo al anochecer."
    assert act.scenes[0].lines[1].text == "Nadie mas lo sabe."


def test_normalization_fills_missing_location_when_events_agree() -> None:
    draft = valid_draft()
    draft.scenes[0].location_id = None
    act = materialize_act(draft, **context())
    assert act.scenes[0].location_id == "archive"


def test_normalization_is_observed_not_rejected() -> None:
    draft = valid_draft()
    draft.scenes[0].cast.append(SceneCastMember(character_id="ana", objective="duplicate"))
    act = materialize_act(draft, **context())
    assert len(act.scenes[0].cast) == 1


def test_event_may_continue_into_the_next_scene() -> None:
    draft = valid_draft()
    draft.scenes[1].event_ids = ["event-1", "event-2"]
    act = materialize_act(draft, **context())
    assert act.scenes[1].event_ids == ["event-1", "event-2"]


def test_absent_participant_is_only_observed() -> None:
    draft = valid_draft()
    draft.scenes[1].cast = [SceneCastMember(character_id="luis", objective="Deny everything")]
    draft.scenes[1].lines = [dialogue("luis", "Yo no fui.")]
    act = materialize_act(draft, **context())
    assert any("ana" in observation for observation in act.observations)


def test_rule_1_unknown_event_id() -> None:
    draft = valid_draft()
    draft.scenes[0].event_ids = ["event-9"]
    with pytest.raises(ValueError, match="unknown event IDs"):
        materialize_act(draft, **context())


def test_rule_2_event_belongs_to_a_different_chapter() -> None:
    plan = make_plan()
    plan.events.append(make_event("event-3", 3, ["ana"]))
    plan.events[-1].chapter_id = "chapter-2"
    draft = valid_draft()
    draft.scenes[0].event_ids = ["event-3"]
    ctx = context()
    ctx["plan"] = plan
    with pytest.raises(ValueError, match="belongs to chapter chapter-2"):
        materialize_act(draft, **ctx)


def test_rule_3_scenes_must_advance_in_plan_order() -> None:
    draft = valid_draft()
    draft.scenes[0], draft.scenes[1] = draft.scenes[1], draft.scenes[0]
    with pytest.raises(ValueError, match="out of order"):
        materialize_act(draft, **context())


def test_rule_4_every_event_must_be_staged() -> None:
    draft = valid_draft()
    draft.scenes = [draft.scenes[0]]
    with pytest.raises(ValueError, match="no scene stages event-2"):
        materialize_act(draft, **context())


def test_rule_5_unknown_location() -> None:
    draft = valid_draft()
    draft.scenes[0].location_id = "dock"
    with pytest.raises(ValueError, match="unknown location dock"):
        materialize_act(draft, **context())


def test_rule_6_scene_events_disagree_on_location() -> None:
    plan = make_plan()
    plan.events[1] = make_event("event-2", 2, ["ana", "luis"])
    plan.events[1].location_id = "harbor"
    ctx = context()
    ctx["plan"] = plan
    ctx["world"] = WorldArtifact(
        setting="x",
        time_period="x",
        rules=["x"],
        locations=[
            Location(id="archive", name="Archive", description="x"),
            Location(id="harbor", name="Harbor", description="x"),
        ],
        atmosphere="x",
    )
    draft = valid_draft()
    draft.scenes[1].event_ids = ["event-1", "event-2"]
    draft.scenes[0].event_ids = []
    draft.scenes[0].event_ids = ["event-1"]
    with pytest.raises(ValueError, match="different locations"):
        materialize_act(draft, **ctx)


def test_rule_7_scene_location_mismatches_its_event() -> None:
    plan = make_plan()
    plan.events[0] = make_event("event-1", 1, ["ana"])
    plan.events[0].location_id = "harbor"
    ctx = context()
    ctx["plan"] = plan
    ctx["world"] = WorldArtifact(
        setting="x",
        time_period="x",
        rules=["x"],
        locations=[
            Location(id="archive", name="Archive", description="x"),
            Location(id="harbor", name="Harbor", description="x"),
        ],
        atmosphere="x",
    )
    draft = valid_draft()
    draft.scenes[0].location_id = "archive"
    with pytest.raises(ValueError, match="take place at harbor"):
        materialize_act(draft, **ctx)


def test_rule_8_unknown_cast_member() -> None:
    draft = valid_draft()
    draft.scenes[0].cast.append(SceneCastMember(character_id="guard", objective="Watch the door"))
    with pytest.raises(ValueError, match="unknown character IDs: guard"):
        materialize_act(draft, **context())


def test_rule_9_dialogue_without_speaker() -> None:
    draft = valid_draft()
    draft.scenes[0].lines[1].speaker_id = ""
    with pytest.raises(ValueError, match="no speaker_id"):
        materialize_act(draft, **context())


def test_rule_10_speaker_not_in_scene_cast() -> None:
    draft = valid_draft()
    draft.scenes[0].lines[1].speaker_id = "luis"
    with pytest.raises(ValueError, match="not in that scene's cast"):
        materialize_act(draft, **context())


def test_direction_speaker_is_normalized_away_not_rejected() -> None:
    draft = valid_draft()
    draft.scenes[0].lines[0] = ScriptLine(
        kind="direction", speaker_id="ana", actor_ids=["ana"], text="Cierra la puerta."
    )
    act = materialize_act(draft, **context())
    assert act.scenes[0].lines[0].speaker_id == ""


def test_rule_12_direction_actor_not_in_cast() -> None:
    draft = valid_draft()
    draft.scenes[0].lines[0] = direction(["luis"])
    with pytest.raises(ValueError, match="not in that scene's cast"):
        materialize_act(draft, **context())


def test_rule_13_act_needs_at_least_one_dialogue_line() -> None:
    draft = valid_draft()
    for scene in draft.scenes:
        scene.lines = [line for line in scene.lines if line.kind != "dialogue"]
    with pytest.raises(ValueError, match="no dialogue line"):
        materialize_act(draft, **context())


def test_rejections_are_ascii() -> None:
    draft = valid_draft()
    draft.scenes[0].event_ids = ["event-9"]
    with pytest.raises(ValueError) as excinfo:
        materialize_act(draft, **context())
    assert str(excinfo.value).isascii()


def test_act_anchor_index_lists_only_legal_ids_in_order() -> None:
    index = act_anchor_index(make_chapter(), make_plan(), make_world(), make_characters())
    assert index.index("event-1") < index.index("event-2")
    assert "archive" in index
    assert "ana" in index and "luis" in index


def test_revision_issue_reports_invalid_candidates() -> None:
    ctx = context()
    original = materialize_act(valid_draft(), **ctx)
    broken = valid_draft()
    broken.scenes[0].event_ids = ["event-9"]
    revised, diagnostic = revision_issue(broken, original, [], **ctx)
    assert revised is None
    assert diagnostic.code == "INVALID_SCRIPT_ACT"


def test_revision_issue_rejects_unchanged_significant_notes() -> None:
    ctx = context()
    original = materialize_act(valid_draft(), **ctx)
    unchanged = valid_draft()
    note = RevisionNote(
        id="note-1",
        priority="major",
        category="pacing",
        evidence="event-2 is rushed",
        instruction="Stage event-2 as a scene",
    )
    revised, diagnostic = revision_issue(unchanged, original, [note], **ctx)
    assert revised is None
    assert diagnostic.code == "UNCHANGED_SIGNIFICANT_NOTES"


def test_revision_issue_accepts_a_valid_change() -> None:
    ctx = context()
    original = materialize_act(valid_draft(), **ctx)
    changed = valid_draft()
    changed.scenes[1].lines[1] = dialogue("luis", "Fui yo. Lo siento.")
    revised, diagnostic = revision_issue(changed, original, [], **ctx)
    assert diagnostic is None
    assert revised is not None
