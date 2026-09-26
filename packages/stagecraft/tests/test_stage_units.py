"""Unit tests for the deterministic half of the performance: no model call anywhere here."""

import pytest
from asg_stagecraft.formats import ActorMemory, NarrativeVoice
from asg_stagecraft.planning.graph import materialize_plan
from asg_stagecraft.planning.profiles import NarrativeProfile
from asg_stagecraft.schemas import (
    CharacterProfile,
    CharactersArtifact,
)
from asg_stagecraft.stage import policy, voices
from asg_stagecraft.stage.casting import (
    fallback_bible,
    gates_for,
    gates_known_by_discoverer,
    materialize_bible,
)
from asg_stagecraft.stage.fallback import narrate
from asg_stagecraft.stage.memory import CharacterMemory
from asg_stagecraft.stage.metrics import simulation_metrics
from asg_stagecraft.stage.perception import visible_text, witnesses
from asg_stagecraft.stage.render import actor_turn_context, scene_log
from asg_stagecraft.stage.schemas import (
    ActorDossier,
    ActorRelationship,
    ActorTurnDraft,
    BeatBrief,
    BeatRecord,
    CastBibleDraft,
    KnowledgeGate,
    PerformanceArtifact,
    PerformanceSettings,
    SceneBrief,
    SceneCastBrief,
    ScenePerformance,
    StageTurn,
)
from asg_stagecraft.stage.stages import _without_act_label
from asg_stagecraft.stage.validation import (
    MAX_SPEECH_WORDS,
    REPETITION_THRESHOLD,
    TurnIssue,
    normalize_turn,
    similarity,
    strip_internal_ids,
    validate_turn,
)
from test_generator_v5 import make_characters, make_world, valid_plan

NAMES = {"ana": "Ana", "bruno": "Bruno", "cora": "Cora"}


def act(**fields) -> ActorTurnDraft:
    """Build an actor draft with a tactic from the closed list unless one is given."""
    return ActorTurnDraft(**{"tactic": "confront", **fields})


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
    draft = act(speech="Aqui estoy.")
    seen = witnesses(
        draft,
        actor_id="ana",
        on_stage=["ana", "bruno"],
        whole_cast=["ana", "bruno", "cora"],
        memory=ActorMemory.OWN,
    )
    assert seen == ["ana", "bruno"]


def test_shared_memory_widens_a_public_turn_to_the_whole_cast() -> None:
    draft = act(speech="Aqui estoy.")
    seen = witnesses(
        draft,
        actor_id="ana",
        on_stage=["ana", "bruno"],
        whole_cast=["ana", "bruno", "cora"],
        memory=ActorMemory.SHARED,
    )
    assert seen == ["ana", "bruno", "cora"]


def test_a_whisper_reaches_only_its_target_even_under_shared_memory() -> None:
    draft = act(speech="No se lo digas.", visibility="whisper", addressed_to=["bruno"])
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
    draft = act(
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
    draft = act(action="Ana limpia sus lentes", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["ana"], actor_name="Ana")
    assert clean.action == "limpia sus lentes"


def test_an_actor_naming_itself_by_its_first_name_is_also_corrected() -> None:
    """Also found live: models drop the first name as often as the full one."""
    draft = act(action="Mara ajusta sus gafas", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["mara"], actor_name="Mara Vela")
    assert clean.action == "ajusta sus gafas"


def test_an_action_that_merely_starts_with_a_verb_is_left_alone() -> None:
    draft = act(action="anota la negativa", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["ana"], actor_name="Ana")
    assert clean.action == "anota la negativa"


def test_a_word_that_merely_begins_with_the_name_is_not_truncated() -> None:
    """Stripping has to respect word boundaries, or Ana loses the start of "Anda"."""
    draft = act(action="Anda hacia la puerta", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["ana"], actor_name="Ana")
    assert clean.action == "Anda hacia la puerta"


def test_an_action_that_is_only_the_name_survives() -> None:
    draft = act(action="Ana", speech="Algo.")
    clean = normalize_turn(draft, on_stage=["ana"], actor_name="Ana")
    assert clean.action == "Ana"


def test_a_whisper_with_nobody_to_hear_it_becomes_public() -> None:
    draft = act(speech="Algo.", visibility="whisper", addressed_to=["fantasma"])
    clean = normalize_turn(draft, on_stage=["ana"])
    assert clean.visibility == "public"


def test_an_empty_turn_is_rejected_in_english_ascii() -> None:
    with pytest.raises(ValueError) as error:
        validate_turn(act(), previous_speech=[])
    assert str(error.value).isascii()
    assert "empty" in str(error.value)


def test_internal_identifiers_are_rejected() -> None:
    draft = act(speech="Esto resuelve event-3.")
    with pytest.raises(ValueError) as error:
        validate_turn(draft, previous_speech=[])
    assert "event-3" in str(error.value)
    assert str(error.value).isascii()


def test_a_repeated_line_is_rejected_and_a_new_one_is_not() -> None:
    earlier = "No pienso ceder en esto, digan lo que digan los demas."
    with pytest.raises(ValueError):
        validate_turn(act(speech=earlier), previous_speech=[earlier])
    validate_turn(
        act(speech="Entonces hagamos otra cosa distinta."),
        previous_speech=[earlier],
    )


def test_every_rejection_carries_the_code_the_audit_files_it_under() -> None:
    with pytest.raises(TurnIssue) as error:
        validate_turn(act(), previous_speech=[])
    assert error.value.code == "EMPTY_TURN"


@pytest.mark.parametrize(
    "action",
    [
        # Both verbatim from the second real run.
        "Me arrodillo lentamente junto al hogar, escarbo las brasas con un hierro viejo.",
        "Golpeo rítmicamente un pequeño bolígrafo metálico contra la palma de mi mano.",
    ],
)
def test_a_first_person_stage_direction_is_rejected(action) -> None:
    with pytest.raises(TurnIssue) as error:
        validate_turn(act(action=action, speech="Algo."), previous_speech=[])
    assert error.value.code == "FIRST_PERSON_ACTION"
    assert str(error.value).isascii()


def test_the_first_person_detector_is_conservative_by_design() -> None:
    """A bare first-person verb gets through: the documented blind spot, not a bug."""
    validate_turn(act(action="Saco una astilla del bolsillo.", speech="Algo."), previous_speech=[])
    validate_turn(act(action="cruza los brazos", speech="Algo."), previous_speech=[])


def test_a_gesture_made_again_is_rejected_even_with_a_word_changed() -> None:
    """Nicolas, second real run: the same tic three times, one adjective apart."""
    earlier = (
        "Se aclara la garganta de forma sonora y empuja sus gafas hacia arriba sobre el puente "
        "de la nariz con el dedo índice."
    )
    again = earlier.replace("sus gafas", "las gafas")
    with pytest.raises(TurnIssue) as error:
        validate_turn(
            act(action=again, speech="Otra cosa."), previous_speech=[], previous_actions=[earlier]
        )
    assert error.value.code == "REPEATED_ACTION"


def test_a_gesture_with_a_clause_tacked_on_is_still_a_repeat() -> None:
    """Julian, first real run: containment, not overlap, is what catches this."""
    earlier = "Consulta un reloj de bolsillo y ajusta los puños de su camisa."
    later = earlier[:-1] + " antes de desplegar un gráfico sobre la mesa."
    with pytest.raises(TurnIssue):
        validate_turn(
            act(action=later, speech="Mire esto."), previous_speech=[], previous_actions=[earlier]
        )


def test_a_new_gesture_is_accepted() -> None:
    validate_turn(
        act(action="abre la ventana de golpe", speech="Algo."),
        previous_speech=[],
        previous_actions=["se ajusta las gafas con el índice"],
    )


def test_a_speech_is_not_a_turn() -> None:
    """Tomas, first real run: 52 words in one breath."""
    speech = (
        "A mí que no me vengan con cuentos de tinta, si la bicha esta se tranca sola es porque "
        "el salitre la pudre todo, y ya me harté de aguantar tanta preguntita estúpida, así que "
        "mejor me voy a la intemperie antes de que este temporal me termine pudriendo a mí "
        "también."
    )
    assert len(speech.split()) > MAX_SPEECH_WORDS
    with pytest.raises(TurnIssue) as error:
        validate_turn(act(speech=speech), previous_speech=[])
    assert error.value.code == "LONG_SPEECH"


def test_a_thought_that_only_restates_the_line_is_emptied() -> None:
    draft = act(
        speech="No pienso abrir esa puerta hasta que llegue el juez.",
        thought="No pienso abrir esa puerta hasta que llegue el juez, pase lo que pase.",
    )
    assert normalize_turn(draft, on_stage=["ana"]).thought == ""


def test_a_thought_that_is_real_subtext_is_kept() -> None:
    draft = act(speech="No pienso abrir esa puerta.", thought="La llave la tengo yo.")
    assert normalize_turn(draft, on_stage=["ana"]).thought == "La llave la tengo yo."


def test_a_tactic_outside_the_closed_list_is_refused_by_the_contract() -> None:
    with pytest.raises(ValueError):
        ActorTurnDraft(speech="Algo.", tactic="presionar")


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


def test_a_world_event_does_not_count_as_anyone_having_moved() -> None:
    """The event carries a placeholder actor; it must not block that actor from answering."""
    history = [
        turn("bruno", speech="Una."),
        turn("ana", action="Se abre la puerta.", number=2).model_copy(update={"kind": "world"}),
    ]
    assert policy.next_actor(on_stage=["ana", "bruno"], turns=history, requested="ana") == "ana"


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
        "public_face": "una mujer joven con uniforme de archivera",
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
                id="gate-1",
                fact="algo",
                known_by=[known],
                revealed_by=known,
                how="confession",
                revealed_at_event_id="no-existe",
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
        knowledge_gates=[
            KnowledgeGate(
                id="gate-1",
                fact="el secreto",
                known_by=[holder],
                revealed_by=holder,
                how="confession",
            )
        ],
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
    assert bible.dossiers[0].public_face == "archivist"


# -- the knowledge boundary: who already knows is not who finds out ------------------------
#
# Frozen from the first real run, whose casting handed the detective the solution before the
# curtain rose, so every deduction she then performed was a recitation.


def gate(**fields) -> KnowledgeGate:
    """Build a gate held by nobody and brought out by the world, unless told otherwise."""
    return KnowledgeGate(**{"id": "gate-1", "fact": "el secreto", "how": "discovery", **fields})


def cast_with(*gates, initial=()):
    plan, characters = plan_and_cast()
    holder = characters.characters[0].id
    draft = CastBibleDraft(
        dossiers=[dossier(holder, initial_knowledge=list(initial))],
        knowledge_gates=list(gates),
    )
    return materialize_bible(draft, cast_ids=[holder], characters=characters, plan=plan)


def test_the_detective_cannot_already_know_what_she_deduces() -> None:
    """The run-1 gate: known_by the detective, who was also the one to deduce it."""
    with pytest.raises(ValueError) as error:
        cast_with(gate(known_by=["ana"], revealed_by="ana", how="deduction"))
    assert "cannot already know" in str(error.value)
    assert str(error.value).isascii()


def test_nobody_confesses_what_they_do_not_know() -> None:
    with pytest.raises(ValueError) as error:
        cast_with(gate(known_by=[], revealed_by="ana", how="confession"))
    assert "confession" in str(error.value)


def test_a_reveal_has_to_tell_somebody_present_something_new() -> None:
    with pytest.raises(ValueError) as error:
        cast_with(
            gate(
                known_by=["ana"],
                revealed_by="ana",
                how="confession",
                revealed_at_event_id="event-1",
            )
        )
    assert "tells nobody anything" in str(error.value)


def test_starting_knowledge_cannot_hand_over_what_the_character_will_deduce() -> None:
    fact = "La lampara se apago con un temporizador escondido en el sotano."
    with pytest.raises(ValueError) as error:
        cast_with(
            gate(fact=fact, revealed_by="ana", how="deduction"),
            initial=["La lampara se apago con un temporizador del sotano."],
        )
    assert "initial_knowledge" in str(error.value)


def test_a_discovery_by_someone_who_did_not_know_is_accepted() -> None:
    bible = cast_with(gate(revealed_by="ana", how="discovery"))
    assert gates_known_by_discoverer(bible) == 0
    assert gates_for(bible, "ana") == []


def test_an_unknown_revealer_is_normalized_to_the_world() -> None:
    bible = cast_with(gate(revealed_by="fantasma", how="discovery"))
    assert bible.knowledge_gates[0].revealed_by == ""


def test_a_dossier_without_a_public_face_is_not_playable() -> None:
    plan, characters = plan_and_cast()
    holder = characters.characters[0].id
    draft = CastBibleDraft(dossiers=[dossier(holder, public_face="")])
    with pytest.raises(ValueError) as error:
        materialize_bible(draft, cast_ids=[holder], characters=characters, plan=plan)
    assert "public_face" in str(error.value)


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


# -- what each reader is shown -----------------------------------------------------------


def brief_with_two():
    return SceneBrief(
        scene_id="chapter-1-scene-1",
        number=1,
        chapter_id="chapter-1",
        act_number=1,
        setting="El faro, de noche.",
        cast=[
            SceneCastBrief(
                character_id="ana",
                name="Ana",
                objective="saber quien entro",
                public_face="inspectora de unos cuarenta anos, abrigo gris",
            ),
            SceneCastBrief(
                character_id="bruno",
                name="Bruno",
                objective="que nadie suba",
                public_face="farero viejo, barba blanca",
            ),
        ],
        beats=[
            BeatBrief(
                event_id="event-1",
                title="t",
                purpose="p",
                outcome="o",
                conflict="c",
            )
        ],
    )


def test_an_actor_sees_who_is_in_front_of_them() -> None:
    """Run 1: with names alone, a woman was called "muchacho" eleven times."""
    context = actor_turn_context(
        scene=brief_with_two(),
        objective="que nadie suba",
        state=None,
        note="",
        gate_facts=[],
        memories=[],
        witnessed=[],
        character_id="bruno",
        names=NAMES,
    )
    assert "CONTIGO EN ESCENA:\n- Ana, inspectora de unos cuarenta anos, abrigo gris" in context
    assert "farero viejo" not in context


def test_the_narrator_log_marks_the_turns_the_beat_turned_on() -> None:
    turns = [turn("ana", speech="Una."), turn("bruno", speech="Dos.", number=2)]
    log = scene_log(turns, NAMES, thoughts=True, key_ids={"chapter-1-scene-1-t002"})
    assert log.splitlines() == ["Ana: Una.", "[clave]", "Bruno: Dos."]


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Acto I: La habitación imposible", "La habitación imposible"),
        ("ACTO III. La revelación", "La revelación"),
        ("La llegada y el encierro", "La llegada y el encierro"),
        ("Actores del faro", "Actores del faro"),
        ("Acto I:", "Acto I:"),
    ],
)
def test_an_act_label_is_dropped_from_a_prose_title(title, expected) -> None:
    assert _without_act_label(title) == expected


# -- honest measurement --------------------------------------------------------------------


def performance_of(turns) -> PerformanceArtifact:
    return PerformanceArtifact(
        language="es",
        settings=PerformanceSettings(
            actor_memory=ActorMemory.OWN,
            turns_per_beat=8,
            check_every=3,
            retrieved_records=6,
            recency_decay=0.25,
            repetition_threshold=REPETITION_THRESHOLD,
        ),
        scenes=[scene_with(turns)],
    )


def measure(turns, story="una dos tres"):
    return simulation_metrics(
        profile=NarrativeProfile.ESSENTIAL,
        performance=performance_of(turns),
        scripted_by_scene={},
        memories={},
        names=NAMES,
        story=story,
        narration_fallbacks=0,
    )


def test_the_metrics_see_the_gestures_the_speech_metric_misses() -> None:
    gesture = "se ajusta las gafas con el dedo indice"
    metrics = measure(
        [
            turn("ana", speech="Primera cosa.", action=gesture),
            turn("bruno", speech="Otra.", number=2),
            turn("ana", speech="Segunda distinta.", action=gesture + " otra vez", number=3),
        ]
    )
    assert metrics.repetition_ratio == 0.0
    assert metrics.action_repetition_ratio == 0.5


def test_the_metrics_count_first_person_actions_and_long_speeches() -> None:
    metrics = measure(
        [
            turn("ana", action="Me arrodillo junto al hogar"),
            turn("bruno", speech=" ".join(["palabra"] * 50), number=2),
        ]
    )
    assert metrics.first_person_actions == 1
    assert metrics.long_speeches == 1


def test_a_standoff_shows_as_a_tactic_streak_and_no_yields() -> None:
    turns = [
        turn(actor, speech=f"linea{number}", number=number).model_copy(
            update={"tactic": "confront" if actor == "ana" else "deny"}
        )
        for number, actor in enumerate(["ana", "bruno"] * 3, 1)
    ]
    metrics = measure(turns)
    assert metrics.max_tactic_streak == 3
    assert metrics.yields == 0


def test_compression_says_whether_the_narrator_curated_or_expanded() -> None:
    turns = [turn("ana", speech="uno dos tres cuatro")]
    assert measure(turns, story="uno dos").compression_ratio == 0.5
    assert measure(turns, story=" ".join(["x"] * 8)).compression_ratio == 2.0


def test_world_events_are_nobody_s_turn_in_the_measurements() -> None:
    thunder = turn("ana", action="Se abre la puerta.").model_copy(update={"kind": "world"})
    metrics = measure([thunder, turn("bruno", speech="Quien anda ahi.", number=2)])
    assert [item.character_id for item in metrics.actor_metrics] == ["bruno"]
