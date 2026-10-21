"""Regression coverage for introductions, scene bridges and spatial source errors."""

import json
from types import SimpleNamespace

import pytest
from asg_stagecraft.agents.orientation import OrientationReview, SpatialReview
from asg_stagecraft.formats import NarrationMethod
from asg_stagecraft.schemas import RevisionNote
from asg_stagecraft.stage.narration_stage import _orientation_preserved
from asg_stagecraft.stage.schemas import ActorTurnDraft, NarrationFinding, NarrationReview
from asg_stagecraft.stage.validation import TurnIssue
from asg_stagecraft.writing.chapter_edits import ParagraphEdit, ParagraphEdits
from asg_stagecraft.writing.orientation import ReaderEvidence, ReaderState, performance_context
from asg_stagecraft.writing.stages import WritingStagesMixin
from stage_fakes import StageFakeProvider
from test_generator_v5 import make_request
from test_simulated_pipeline import generate, read_json
from test_stage_engine import Stage, scene, shown

CONTEXT = {
    "characters": [{"id": "nola"}, {"id": "vrak"}, {"id": "caelen"}],
    "places": [{"id": "valle"}, {"id": "garganta"}, {"id": "pantano"}],
}
INTRO = "Nola, la anciana herbívora de marcas ceremoniales, vigilaba el valle."


def test_only_prose_evidence_counts_as_an_introduction():
    state = ReaderState()
    evidence = ReaderEvidence(kind="character", entity_id="nola", quote=INTRO)
    state.accept([evidence], "Nola señaló la piedra. Vrak respondió.", CONTEXT, 1)
    assert state.characters == {}  # The simulation's cast does not introduce either character.
    state.accept([evidence], INTRO, CONTEXT, 2)
    state.accept([evidence], INTRO, CONTEXT, 3)
    assert state.characters["nola"]["chapter"] == 2
    assert "vrak" not in state.characters


def test_unknown_entities_and_unsupported_positions_never_enter_memory():
    state = ReaderState()
    entries = [
        ReaderEvidence(kind="character", entity_id="stranger", quote=INTRO),
        ReaderEvidence(kind="position", entity_id="nola", location_id="templo", quote=INTRO),
        ReaderEvidence(kind="character", entity_id="nola", quote="Nola"),
    ]
    state.accept(entries, INTRO, CONTEXT, 1)
    assert state.as_record() == {"characters": {}, "places": {}, "positions": {}}


@pytest.mark.parametrize("origin,destination", [("valle", "garganta"), ("pantano", "valle")])
def test_last_position_updates_only_after_a_narrated_arrival(origin, destination):
    state = ReaderState()
    first = f"Nola aguardaba junto al {origin} silencioso."
    second = f"Más tarde Nola llegó al {destination}."
    state.accept(
        [ReaderEvidence(kind="position", entity_id="nola", location_id=origin, quote=first)],
        first,
        CONTEXT,
        1,
    )
    arrival = ReaderEvidence(
        kind="position", entity_id="nola", location_id=destination, quote=second
    )
    state.accept([arrival], "Entretanto Vrak conversaba con Keth.", CONTEXT, 2)
    assert state.positions["nola"]["location_id"] == origin
    state.accept([arrival], second, CONTEXT, 3)
    assert state.positions["nola"]["location_id"] == destination


@pytest.mark.parametrize("method", [NarrationMethod.REPORTED, NarrationMethod.SELECTED])
def test_missing_context_uses_second_narration_and_preserves_best_faithful_prose(tmp_path, method):
    bare = "Nola señaló la piedra. Vrak respondió con un siseo."
    finding = NarrationFinding(
        code="CHARACTER_CONTEXT",
        quote="Nola señaló la piedra",
        correction="Introduce her public identity and ceremonial marks.",
    )
    provider = StageFakeProvider(
        narrator_outputs=[bare, INTRO],
        narration_reviews=[NarrationReview(findings=[finding]), NarrationReview()],
    )
    run, _ = generate(tmp_path, provider, narration_method=method, audio=False)
    chapter = (run.run_dir / "narration/chapter-001.md").read_text(encoding="utf-8")
    assert chapter.strip() == INTRO
    assert read_json(run, "narration.json")["chapters"][0]["attempts"] == 2
    assert read_json(run, "narration.json")["chapters"][0]["source"] == "narrator"


def test_unchanged_orientation_issue_does_not_replace_prose_with_a_transcript(tmp_path):
    body = "Caelen extendió el musgo. Gonzalo aceptó la oferta."
    review = NarrationReview(
        findings=[
            NarrationFinding(
                code="CHARACTER_CONTEXT",
                quote="Caelen extendió el musgo",
                correction="Establish Caelen's public identity at this appearance.",
            )
        ]
    )
    provider = StageFakeProvider(narrator_outputs=[body, body], narration_reviews=[review, review])
    run, _ = generate(tmp_path, provider, audio=False)
    assert (run.run_dir / "narration/chapter-001.md").read_text(encoding="utf-8").strip() == body
    assert any(
        "READER_CONTEXT_UNRESOLVED" in warning
        for warning in read_json(run, "metadata.json")["warnings"]
    )


def test_line_edit_cannot_erase_the_only_character_introduction():
    before = NarrationReview(
        reader_evidence=[
            ReaderEvidence(
                kind="character",
                entity_id="nola",
                quote=INTRO,
            )
        ]
    )
    assert not _orientation_preserved(
        before, NarrationReview(), INTRO, "Nola vigilaba el valle.", [], {}
    )
    assert not _orientation_preserved(before, None, INTRO, INTRO, [], {})


def test_a_helm_in_the_temple_is_rejected_at_the_source():
    setting = "El altar mayor del Templo de las Plumas."
    action = "Gonzalo empuñó el timón del barco."
    review = SpatialReview(
        action_quote=action,
        context_quote=setting,
        correction="Remain at the altar; the helm is not here.",
    )
    engine = Stage(lambda mode, context: shown(context)).engine(review_space=lambda *_: review)
    with pytest.raises(TurnIssue, match="helm") as caught:
        engine._check_space(
            ActorTurnDraft(action=action, tactic="test"),
            scene().model_copy(update={"setting": setting}),
            [],
        )
    assert caught.value.code == "SPATIAL_CONTINUITY"


def test_uncited_spatial_rejection_cannot_discard_an_action():
    review = SpatialReview(
        action_quote="invented quote", context_quote="unknown room", correction="Move elsewhere"
    )
    engine = Stage(lambda mode, context: shown(context)).engine(review_space=lambda *_: review)
    engine._check_space(
        ActorTurnDraft(tactic="test", action="Recuerda el timón de su barco."), scene(), []
    )


class MemoryRepository:
    """Keep orientation audit artifacts without running an entire generation."""

    def __init__(self):
        self.records = {}
        self.warnings = []

    def save_json(self, name, value):
        self.records[name] = value.model_dump(mode="json")

    def save_data(self, name, value):
        self.records[name] = value

    def add_warning(self, warning):
        self.warnings.append(warning)


@pytest.mark.parametrize("faithful", [True, False])
def test_top_down_repairs_context_but_rejects_an_invented_journey(faithful):
    original = "Nola señaló la piedra del valle."
    note = RevisionNote(
        id="introduce-nola",
        priority="major",
        category="world_continuity",
        evidence=original,
        instruction="Establish Nola's public identity.",
    )
    responses = [
        OrientationReview(notes=[note]),
        OrientationReview(
            faithful=faithful,
            reader_evidence=[
                ReaderEvidence(
                    kind="character",
                    entity_id="nola",
                    quote=INTRO,
                )
            ],
        ),
    ]

    class Provider:
        def generate_structured(self, *, schema, **kwargs):
            if schema is ParagraphEdits:
                return ParagraphEdits(
                    edits=[
                        ParagraphEdit(
                            note_ids=[note.id],
                            paragraph="P1",
                            action="replace",
                            text=INTRO,
                        )
                    ]
                )
            return responses.pop(0)

    host = SimpleNamespace(
        provider=Provider(),
        repository=MemoryRepository(),
        _call_agent=lambda name, function: function(),
    )
    reader = ReaderState()
    result = WritingStagesMixin._orient_chapter(
        host, make_request(), original, CONTEXT, reader, 1, "final"
    )
    assert result == (INTRO if faithful else original)
    assert ("nola" in reader.characters) is faithful


def test_old_narration_reviews_remain_readable():
    assert NarrationReview.model_validate(json.loads('{"findings": []}')).reader_evidence == []


@pytest.mark.parametrize("method", [NarrationMethod.REPORTED, NarrationMethod.SELECTED])
def test_reader_context_survives_between_chapters_in_both_narration_methods(tmp_path, method):
    intro = "Ana, la archivera de manos manchadas de tinta, abrió la puerta."
    first_review = NarrationReview(
        reader_evidence=[
            ReaderEvidence(
                kind="character",
                entity_id="ana",
                quote=intro,
            )
        ]
    )
    provider = StageFakeProvider(narrator_outputs=[intro], narration_reviews=[first_review])
    run, _ = generate(tmp_path, provider, narration_method=method, audio=False)
    state = read_json(run, "narration/chapter-001-reader-state.json")
    assert state["characters"]["ana"]["quote"] == intro
    assert intro in provider.narrator_prompts[1]
    assert '"chapter": 1' in provider.narrator_prompts[1]


def test_a_missing_spatial_reviewer_is_visible_but_does_not_invent_a_rejection():
    def unavailable(*args):
        raise RuntimeError("offline")

    engine = Stage(lambda mode, context: shown(context)).engine(review_space=unavailable)
    turn = ActorTurnDraft(action="Observa la puerta cerrada.", tactic="test")
    engine._check_space(turn, scene(), [])
    engine._check_space(turn, scene(), [])
    assert sum("SPATIAL_REVIEW_UNAVAILABLE" in item for item in engine.warnings) == 1


def test_context_for_a_limited_view_contains_no_hidden_scene_or_private_dossier():
    seen = SimpleNamespace(
        id="seen",
        location_id="valle",
        setting="El valle de helechos.",
        cast=[SimpleNamespace(character_id="nola")],
    )
    hidden = SimpleNamespace(
        id="hidden",
        location_id="temple",
        setting="Secret chamber.",
        cast=[SimpleNamespace(character_id="vrak")],
    )
    play = SimpleNamespace(
        acts=[SimpleNamespace(scenes=[seen, hidden])],
        cast=[
            SimpleNamespace(character_id="nola", name="Nola"),
            SimpleNamespace(character_id="vrak", name="Vrak"),
        ],
    )
    bible = SimpleNamespace(
        dossiers=[
            SimpleNamespace(
                character_id="nola",
                public_face="Anciana herbívora con marcas ceremoniales.",
                secret="Knows the hidden chamber's password.",
            )
        ]
    )
    context = performance_context(
        [SimpleNamespace(scene_id="seen")], play, bible, None, ReaderState()
    )
    text = json.dumps(context)
    assert "password" not in text and "Secret chamber" not in text
    assert [c["id"] for c in context["characters"]] == ["nola"]
    assert [p["id"] for p in context["places"]] == ["valle"]


def test_rejected_spatial_action_reaches_actor_retry_and_never_enters_history():
    setting = "El altar mayor del templo, lejos del barco."
    invalid = "Gonzalo empuña el timón del barco."
    stage = Stage(lambda mode, context: shown(context))
    rejections, feedback_seen = [], []
    engine = stage.engine(
        on_rejection=rejections.append,
        review_space=lambda context, action: (
            SpatialReview(
                action_quote=invalid,
                context_quote=setting,
                correction="Stay at the altar; the helm remains on the ship.",
            )
            if action == invalid
            else SpatialReview()
        ),
    )

    def propose(system, context, feedback):
        feedback_seen.append(feedback)
        if len(feedback_seen) == 1:
            return ActorTurnDraft(action=invalid, tactic="test")
        return stage.take_turn(system, context, feedback)

    engine.take_turn = propose
    performed = engine.perform_scene(scene().model_copy(update={"setting": setting}))
    assert any(item.code == "SPATIAL_CONTINUITY" for item in rejections)
    assert any("helm" in feedback for feedback in feedback_seen)
    assert all(turn.action != invalid for turn in performed.turns)


def test_previous_pipeline_version_can_be_reused_for_comparison(tmp_path):
    from asg_stagecraft.pipeline import _compatible_source

    (tmp_path / "metadata.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "pipeline_version": "7.20",
                "story_format": "simulated",
            }
        ),
        encoding="utf-8",
    )
    assert _compatible_source(tmp_path, simulated=True)["pipeline_version"] == "7.20"
