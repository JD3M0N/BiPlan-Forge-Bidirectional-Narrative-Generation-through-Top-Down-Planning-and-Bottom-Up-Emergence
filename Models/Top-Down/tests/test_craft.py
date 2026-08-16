import pytest
from pydantic import ValidationError

from asg_top_down.craft import (
    normalize_audit, try_fail_target, validate_craft_characters,
    validate_craft_contract, validate_craft_outline,
)
from asg_top_down.schemas import (
    Character, CharacterMilestone, CharacterSliderArc, CharactersArtifact,
    CraftAuditAnswer, CraftAuditArtifact, CraftBeat, CraftContractArtifact,
    CraftPromise, ChapterPlan, PlotNodeReview, SliderRange, StoryOutlineArtifact,
    TryFailCycle,
)


def _characters() -> CharactersArtifact:
    return CharactersArtifact(characters=[Character(
        name="Ada", narrative_role="protagonist", jungian_archetype="explorer",
        goal="revelar", motivation="proteger", conflict="censura", arc="actúa",
        importance="main", slider_arc=CharacterSliderArc(
            sympathy=SliderRange(start=8, target=8, rationale="Es cercana"),
            competence=SliderRange(start=7, target=7, rationale="Sabe investigar"),
            proactivity=SliderRange(start=3, target=8, rationale="Aprende a actuar"),
            focus="proactivity", direction="ascending", justification="Toma el control",
        ),
    )])


def _contract() -> CraftContractArtifact:
    return CraftContractArtifact(try_fail_target=2, promises=[
        CraftPromise(id="tone", kind="tone", statement="Tensión", setup="Amenaza",
                     progress_signals=["Peligro"], payoff="Alivio"),
        CraftPromise(id="plot", kind="plot", statement="Resolver", setup="Pregunta",
                     progress_signals=["Pista"], payoff="Respuesta"),
        CraftPromise(id="ada", kind="character", character_name="Ada", statement="Actuará",
                     setup="Duda", progress_signals=["Se arriesga"], payoff="Decide"),
    ])


def _outline() -> StoryOutlineArtifact:
    return StoryOutlineArtifact(premise="Señal", synopsis="Ada actúa", chapters=[ChapterPlan(
        id="ch1", order=1, title="Señal", abstract="Ada investiga", target_words=450,
        freytag_phases=["exposition", "climax", "denouement"],
        craft_beats=[
            CraftBeat(id=f"{promise}-{kind}", promise_id=promise, kind=kind,
                      description=f"{kind} {promise}")
            for promise in ("tone", "plot", "ada")
            for kind in ("setup", "progress", "payoff")
        ],
        character_milestones=[
            CharacterMilestone(id=f"ada-{stage}", character_name="Ada", stage=stage,
                focus_slider="proactivity", demonstrated_value=value, description=stage)
            for stage, value in (("start", 3), ("transition", 5), ("end", 8))
        ],
        try_fail_cycles=[
            TryFailCycle(id="tf1", action="Copia", outcome="yes_but",
                         consequence="La detectan", promise_id="plot"),
            TryFailCycle(id="tf2", action="Transmite", outcome="no_and",
                         consequence="La bloquean", promise_id="plot"),
        ],
    )])


@pytest.mark.parametrize("words, expected", [(300, 2), (4000, 2), (4001, 3), (20000, 7)])
def test_try_fail_target_scales_with_length(words, expected):
    assert try_fail_target(words) == expected


def test_focus_slider_must_change_in_its_declared_direction():
    with pytest.raises(ValidationError, match="must change"):
        CharacterSliderArc(
            sympathy=SliderRange(start=5, target=5, rationale="estable"),
            competence=SliderRange(start=5, target=5, rationale="estable"),
            proactivity=SliderRange(start=5, target=5, rationale="estable"),
            focus="proactivity", direction="ascending", justification="arco",
        )


def test_production_characters_require_a_main_slider_arc():
    legacy = CharactersArtifact(characters=[Character(
        name="Ada", narrative_role="protagonist", jungian_archetype="explorer",
        goal="x", motivation="x", conflict="x", arc="x",
    )])
    with pytest.raises(ValueError, match="at least one main"):
        validate_craft_characters(legacy)


def test_contract_and_outline_pass_cross_artifact_validation():
    characters, contract, outline = _characters(), _contract(), _outline()
    validate_craft_contract(contract, characters, 450)
    validate_craft_outline(outline, contract, characters)


def test_contract_rejects_missing_main_character_promise():
    contract = _contract().model_copy(deep=True)
    contract.promises[-1].character_name = "Otra"
    with pytest.raises(ValueError, match="main cast exactly"):
        validate_craft_contract(contract, _characters(), 450)


def test_outline_rejects_unknown_promise_reference():
    outline = _outline()
    outline.chapters[0].craft_beats[0].promise_id = "unknown"
    with pytest.raises(ValueError, match="unknown promise"):
        validate_craft_outline(outline, _contract(), _characters())


def test_missing_critic_answer_becomes_a_blocking_failure():
    raw = CraftAuditArtifact(summary="incompleta", answers=[CraftAuditAnswer(
        question_id="known", category="global", subject_id="story", question="Known?",
        verdict="pass", evidence="Sí",
    )])
    expected = [
        {"question_id": "known", "category": "global", "subject_id": "story",
         "question": "Known?", "blocking": True},
        {"question_id": "missing", "category": "global", "subject_id": "story",
         "question": "Missing?", "blocking": True},
    ]
    normalized = normalize_audit(raw, expected)
    assert normalized.passed is False
    assert normalized.failed_blocking_ids == ["missing"]


def test_contradictory_accepted_review_is_normalized_to_rejection():
    review = PlotNodeReview(
        accepted=True, causal=True, intentional=True, conflict_present=True,
        continuous=False, novel=True, advances_ending=True, world_consistent=True,
    )
    assert review.accepted is False
    assert any("continuous" in issue for issue in review.issues)


def test_explicit_rejection_is_never_promoted():
    review = PlotNodeReview(
        accepted=False, causal=True, intentional=True, conflict_present=True,
        continuous=True, novel=True, advances_ending=True, world_consistent=True,
    )
    assert review.accepted is False
    assert review.issues
