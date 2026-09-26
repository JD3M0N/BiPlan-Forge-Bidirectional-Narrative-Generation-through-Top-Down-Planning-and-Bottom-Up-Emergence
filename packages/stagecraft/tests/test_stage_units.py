"""Unit tests for the deterministic half of the performance: no model call anywhere here."""

import pytest
from asg_stagecraft.formats import ActorMemory, NarrativeVoice
from asg_stagecraft.planning.graph import materialize_plan
from asg_stagecraft.schemas import (
    CharacterProfile,
    CharactersArtifact,
)
from asg_stagecraft.stage import policy, voices
from asg_stagecraft.stage.casting import fallback_bible, gates_for, materialize_bible
from asg_stagecraft.stage.fallback import narrate
from asg_stagecraft.stage.memory import CharacterMemory
from asg_stagecraft.stage.perception import visible_text, witnesses
from asg_stagecraft.stage.schemas import (
    ActorDossier,
    ActorRelationship,
    ActorTurnDraft,
    BeatRecord,
    CastBibleDraft,
    KnowledgeGate,
    ScenePerformance,
    StageTurn,
)
from asg_stagecraft.stage.validation import (
    REPETITION_THRESHOLD,
    normalize_turn,
    similarity,
    strip_internal_ids,
    validate_turn,
)
from test_generator_v5 import make_characters, make_world, valid_plan

NAMES = {"ana": "Ana", "bruno": "Bruno", "cora": "Cora"}


def turn(
    actor_id, *, speech="", action="", thought="", visibility="public", addressed=(), number=1
):
    return StageTurn(
        id=f"chapter-1-scene-1-t{number:03d}",
        scene_id="chapter-1-scene-1",
        number=number,
        actor_id=actor_id,
        beat_index=0,
        beat_event_id="event-1",
        witnesses=[actor_id, *addressed] if visibility == "whisper" else list(NAMES),
        speech=speech,
        action=action,
        thought=thought,
        visibility=visibility,
        addressed_to=list(addressed),
    )


# -- perception --------------------------------------------------------------------------


def test_a_public_turn_is_witnessed_by_everyone_on_stage() -> None:
    draft = ActorTurnDraft(speech="Aqui estoy.")
    seen = witnesses(
        draft,
        actor_id="ana",
        on_stage=["ana", "bruno"],
        whole_cast=["ana", "bruno", "cora"],
        memory=ActorMemory.OWN,
    )
    assert seen == ["ana", "bruno"]


def test_shared_memory_widens_a_public_turn_to_the_whole_cast() -> None:
    draft = ActorTurnDraft(speech="Aqui estoy.")
    seen = witnesses(
        draft,
        actor_id="ana",
        on_stage=["ana", "bruno"],
        whole_cast=["ana", "bruno", "cora"],
        memory=ActorMemory.SHARED,
    )
    assert seen == ["ana", "bruno", "cora"]


def test_a_whisper_reaches_only_its_target_even_under_shared_memory() -> None:
    draft = ActorTurnDraft(speech="No se lo digas.", visibility="whisper", addressed_to=["bruno"])
    for memory in (ActorMemory.OWN, ActorMemory.SHARED):
        seen = witnesses(
            draft,
            actor_id="ana",
            on_stage=["ana", "bruno", "cora"],
            whole_cast=["ana", "bruno", "cora"],
            memory=memory,
        )
        assert seen == ["ana", "bruno"], memory


def test_a_thought_is_visible_only_to_the_character_who_thought_it() -> None:
    thinking = turn("ana", speech="Nada.", thought="Miente.")
    assert "pienso" in visible_text(thinking, "ana", NAMES)
    assert "Miente" not in visible_text(thinking, "bruno", NAMES)


# -- memory ------------------------------------------------------------------------------


def test_memory_only_recalls_earlier_scenes_and_scores_deterministically() -> None:
    memory = CharacterMemory("ana")
    memory.remember(kind="observed", text="Bruno quemo el expediente", scene_number=1)
    memory.remember(kind="observed", text="Cora trajo cafe", scene_number=1)
    memory.remember(kind="observed", text="algo de la escena actual", scene_number=2)
    first = memory.recall("expediente quemado", scene_number=2, turn_number=1, present=["bruno"])
    second = memory.recall("expediente quemado", scene_number=2, turn_number=1, present=["bruno"])
    assert [item.id for item in first] == [item.id for item in second]
    assert all(item.scene_number < 2 for item in first)
    assert any("expediente" in item.text for item in first)


def test_recency_favours_the_nearer_of_two_equally_relevant_memories() -> None:
    memory = CharacterMemory("ana")
    old = memory.remember(kind="observed", text="la llave estaba en el cajon", scene_number=1)
    new = memory.remember(kind="observed", text="la llave estaba en el cajon", scene_number=5)
    memory.recall("la llave", scene_number=6, turn_number=1, present=[])
    scores = {item.record_id: item.recency for item in memory.retrievals}
    assert scores[new.id] > scores[old.id]


def test_two_characters_never_share_a_memory_stream() -> None:
    ana, bruno = CharacterMemory("ana"), CharacterMemory("bruno")
    ana.remember(kind="thought", text="se donde esta la copia", scene_number=1)
    assert bruno.recall("la copia", scene_number=2, turn_number=1, present=[]) == []


def test_reflections_always_travel_however_they_score() -> None:
    memory = CharacterMemory("ana")
    for index in range(8):
        memory.remember(kind="observed", text=f"ruido irrelevante {index}", scene_number=1)
    memory.remember(kind="reflection", text="aprendi que no puedo fiarme", scene_number=1)
    recalled = memory.recall("cualquier cosa", scene_number=2, turn_number=1, present=[])
    assert any(item.kind == "reflection" for item in recalled)


# -- validation --------------------------------------------------------------------------


def test_normalization_fixes_what_has_one_correct_reading() -> None:
    draft = ActorTurnDraft(
        speech='  "—Nadie mas lo sabe."  ',
        action="(da un paso)",
        visibility="whisper",
        addressed_to=["nadie", "bruno"],
    )
    clean = normalize_turn(draft, on_stage=["ana", "bruno"])
    assert clean.speech == "Nadie mas lo sabe."
    assert clean.action == "da un paso"
    assert clean.addressed_to == ["bruno"]


def test_an_actor_naming_itself_in_its_own_action_is_corrected() -> None:
    """Found on the first real run: every renderer already prefixes the performer's name."""
    draft = ActorTurnDraft(action="Ana limpia sus lentes", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["ana"], actor_name="Ana")
    assert clean.action == "limpia sus lentes"


def test_an_actor_naming_itself_by_its_first_name_is_also_corrected() -> None:
    """Also found live: models drop the first name as often as the full one."""
    draft = ActorTurnDraft(action="Mara ajusta sus gafas", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["mara"], actor_name="Mara Vela")
    assert clean.action == "ajusta sus gafas"


def test_an_action_that_merely_starts_with_a_verb_is_left_alone() -> None:
    draft = ActorTurnDraft(action="anota la negativa", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["ana"], actor_name="Ana")
    assert clean.action == "anota la negativa"


def test_a_word_that_merely_begins_with_the_name_is_not_truncated() -> None:
    """Stripping has to respect word boundaries, or Ana loses the start of "Anda"."""
    draft = ActorTurnDraft(action="Anda hacia la puerta", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["ana"], actor_name="Ana")
    assert clean.action == "Anda hacia la puerta"


def test_an_action_that_is_only_the_name_survives() -> None:
    draft = ActorTurnDraft(action="Ana", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["ana"], actor_name="Ana")
    assert clean.action == "Ana"


def test_a_whisper_with_nobody_to_hear_it_becomes_public() -> None:
    draft = ActorTurnDraft(speech="Algo.", visibility="whisper", addressed_to=["fantasma"])
    clean = normalize_turn(draft, on_stage=["ana"])
    assert clean.visibility == "public"


def test_an_empty_turn_is_rejected_in_english_ascii() -> None:
    with pytest.raises(ValueError) as error:
        validate_turn(ActorTurnDraft(), previous_speech=[], beat_count=1)
    assert str(error.value).isascii()
    assert "empty" in str(error.value)


def test_internal_identifiers_are_rejected() -> None:
    draft = ActorTurnDraft(speech="Esto resuelve event-3.")
    with pytest.raises(ValueError) as error:
        validate_turn(draft, previous_speech=[], beat_count=1)
    assert "event-3" in str(error.value)
    assert str(error.value).isascii()


def test_a_repeated_line_is_rejected_and_a_new_one_is_not() -> None:
    earlier = "No pienso ceder en esto, digan lo que digan los demas."
    with pytest.raises(ValueError):
        validate_turn(ActorTurnDraft(speech=earlier), previous_speech=[earlier], beat_count=1)
    validate_turn(
        ActorTurnDraft(speech="Entonces hagamos otra cosa distinta."),
        previous_speech=[earlier],
        beat_count=1,
    )


def test_similarity_is_symmetric_and_bounded() -> None:
    assert similarity("la copia del archivo", "la copia del archivo") == 1.0
    assert similarity("", "algo") == 0.0
    assert 0.0 <= similarity("la copia", "el archivo") <= 1.0
    assert similarity("a b c", "b c d") == similarity("b c d", "a b c")


def test_stripping_identifiers_leaves_readable_text() -> None:
    assert strip_internal_ids("Resolve event-2 before chapter-1") == "Resolve before"
    assert strip_internal_ids("nothing to strip") == "nothing to strip"


def test_the_repetition_threshold_is_stricter_than_ibsen_reported_sufficient() -> None:
    assert REPETITION_THRESHOLD > 0.4


def test_what_the_world_does_is_never_attributed_to_a_character() -> None:
    """The director's intervention is the stage acting, not whoever stood there first."""
    thunder = turn("ana", action="Un trueno apaga la lampara.").model_copy(update={"kind": "world"})
    assert visible_text(thunder, "bruno", NAMES) == "(Un trueno apaga la lampara.)"
    assert "Ana" not in narrate([thunder], NAMES)
    assert "Un trueno apaga la lampara." in narrate([thunder], NAMES)


# -- turn order --------------------------------------------------------------------------


def test_the_director_pick_wins_when_it_is_available() -> None:
    assert policy.next_actor(on_stage=["ana", "bruno"], turns=[], requested="bruno") == "bruno"


def test_nobody_speaks_twice_in_a_row_while_another_could() -> None:
    history = [turn("ana", speech="Una.")]
    assert policy.next_actor(on_stage=["ana", "bruno"], turns=history) == "bruno"


def test_a_lone_character_may_continue_alone() -> None:
    history = [turn("ana", speech="Una.")]
    assert policy.next_actor(on_stage=["ana"], turns=history) == "ana"


def test_whoever_was_addressed_answers_next() -> None:
    history = [turn("ana", speech="Y tu?", addressed=["cora"], visibility="public")]
    assert policy.next_actor(on_stage=["ana", "bruno", "cora"], turns=history) == "cora"


def test_a_scene_without_a_cast_is_a_programming_error() -> None:
    with pytest.raises(ValueError):
        policy.next_actor(on_stage=[], turns=[])


def test_the_beat_is_checked_periodically_and_forced_at_its_budget() -> None:
    assert not policy.should_check(1)
    assert policy.should_check(policy.CHECK_EVERY)
    assert not policy.must_force(7, turns_per_beat=8)
    assert policy.must_force(8, turns_per_beat=8)


# -- voices ------------------------------------------------------------------------------


def scene_with(turns):
    return ScenePerformance(
        scene_id="chapter-1-scene-1",
        number=1,
        chapter_id="chapter-1",
        turns=turns,
        beats=[BeatRecord(event_id="event-1", index=0, achieved=True)],
    )


def test_the_omniscient_narrator_keeps_every_thought() -> None:
    scene = scene_with(
        [turn("ana", speech="A.", thought="X"), turn("bruno", speech="B.", thought="Y", number=2)]
    )
    visible = voices.visible_turns(NarrativeVoice.OMNISCIENT, scene)
    assert [item.thought for item in visible] == ["X", "Y"]


def test_the_focalized_narrator_keeps_only_the_focal_thoughts() -> None:
    scene = scene_with(
        [
            turn("ana", speech="A.", thought="X"),
            turn("ana", speech="A2.", thought="X2", number=2),
            turn("bruno", speech="B.", thought="Y", number=3),
        ]
    )
    visible = voices.visible_turns(NarrativeVoice.FOCALIZED, scene)
    assert voices.focal_character(scene) == "ana"
    assert [item.thought for item in visible] == ["X", "X2", ""]


def test_the_first_person_narrator_only_sees_what_it_witnessed() -> None:
    unseen = turn(
        "bruno",
        speech="A escondidas.",
        thought="Y",
        visibility="whisper",
        addressed=["cora"],
        number=2,
    )
    scene = scene_with([turn("ana", speech="A.", thought="X"), unseen])
    visible = voices.visible_turns(NarrativeVoice.FIRST_PERSON, scene, narrator="ana")
    assert [item.id for item in visible] == ["chapter-1-scene-1-t001"]


def test_only_the_first_person_voice_needs_a_narrator() -> None:
    scene = scene_with([turn("ana", speech="A.")])
    assert voices.narrator_character(NarrativeVoice.OMNISCIENT, [scene]) == ""
    assert voices.narrator_character(NarrativeVoice.FIRST_PERSON, [scene]) == "ana"
    assert (
        voices.narrator_character(NarrativeVoice.FIRST_PERSON, [scene], protagonist="cora")
        == "cora"
    )


# -- casting -----------------------------------------------------------------------------


def dossier(character_id, **kwargs):
    fields = {
        "character_id": character_id,
        "want": "algo concreto",
        "voice": "habla corto",
    }
    fields.update(kwargs)
    return ActorDossier(**fields)


def plan_and_cast():
    characters = make_characters()
    plan = materialize_plan(valid_plan(), make_world(), characters)
    return plan, characters


def test_a_bible_missing_a_dossier_is_rejected_in_english() -> None:
    plan, characters = plan_and_cast()
    draft = CastBibleDraft(dossiers=[dossier("ana")])
    with pytest.raises(ValueError) as error:
        materialize_bible(draft, cast_ids=["ana", "bruno"], characters=characters, plan=plan)
    assert str(error.value).isascii()
    assert "bruno" in str(error.value)


def test_unknown_relationships_are_dropped_rather_than_rejected() -> None:
    plan, characters = plan_and_cast()
    known = characters.characters[0].id
    draft = CastBibleDraft(
        dossiers=[
            dossier(
                known,
                relationships=[
                    ActorRelationship(character_id="fantasma", stance="wary", wants_from_them="x"),
                    ActorRelationship(character_id=known, stance="self", wants_from_them="x"),
                ],
            )
        ]
    )
    bible = materialize_bible(draft, cast_ids=[known], characters=characters, plan=plan)
    assert bible.dossiers[0].relationships == []


def test_a_gate_anchored_to_an_unknown_event_is_rejected() -> None:
    plan, characters = plan_and_cast()
    known = characters.characters[0].id
    draft = CastBibleDraft(
        dossiers=[dossier(known)],
        knowledge_gates=[
            KnowledgeGate(
                id="gate-1", fact="algo", known_by=[known], revealed_at_event_id="no-existe"
            )
        ],
    )
    with pytest.raises(ValueError) as error:
        materialize_bible(draft, cast_ids=[known], characters=characters, plan=plan)
    assert "no-existe" in str(error.value)


def test_a_gate_only_reaches_the_characters_that_hold_it() -> None:
    plan, characters = plan_and_cast()
    holder = characters.characters[0].id
    draft = CastBibleDraft(
        dossiers=[dossier(holder)],
        knowledge_gates=[KnowledgeGate(id="gate-1", fact="el secreto", known_by=[holder])],
    )
    bible = materialize_bible(draft, cast_ids=[holder], characters=characters, plan=plan)
    assert gates_for(bible, holder) == ["el secreto"]
    assert gates_for(bible, "quien-sea") == []


def test_the_fallback_bible_is_playable_and_says_it_is_a_fallback() -> None:
    characters = CharactersArtifact(
        characters=[
            CharacterProfile(
                id="ana",
                name="Ana",
                role="archivist",
                goal="find the file",
                motivation="guilt",
                conflict="loyalty against truth",
                arc="from silence to speech",
                voice="clipped",
            )
        ]
    )
    bible = fallback_bible(["ana"], characters)
    assert bible.fallback is True
    assert bible.dossiers[0].want == "find the file"
    assert bible.dossiers[0].voice == "clipped"


# -- the deterministic narrator ----------------------------------------------------------


def test_the_fallback_narrator_renders_speech_action_and_thought() -> None:
    prose = narrate(
        [turn("ana", speech="Nadie mas lo sabe.", action="cierra el archivo", thought="Miente")],
        NAMES,
    )
    assert "—Nadie mas lo sabe —dijo Ana." in prose
    assert "Ana cierra el archivo." in prose
    assert "Ana penso que miente." in prose


def test_the_fallback_narrator_invents_nothing_for_an_empty_log() -> None:
    assert narrate([], NAMES) == ""
