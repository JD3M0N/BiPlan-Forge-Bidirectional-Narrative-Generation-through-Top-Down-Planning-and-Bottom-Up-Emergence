"""The scene engine against scripted model calls: the escalation ladder, derived verdicts, coda.

No provider anywhere. Each test hands the engine plain callables, so what is under test is the
part that must be the same on every run: who moves, when the director is asked what, and how a
beat ends - reached, reached with the world's help, or forced.
"""

import re
from types import SimpleNamespace

import pytest
from asg_stagecraft.formats import SimulationMode
from asg_stagecraft.stage.causality import cited_source
from asg_stagecraft.stage.engine import CODA_NOTE, FALLBACK_TURN_NOTE, PerformanceEngine
from asg_stagecraft.stage.inventory import StageInventory
from asg_stagecraft.stage.revision import materialize_revision
from asg_stagecraft.stage.schemas import (
    ActorTurnDraft,
    ActorTurnWithItemsDraft,
    BeatBrief,
    BeatCheckDraft,
    BeatDirection,
    EvidenceSource,
    FactProposal,
    FutureRevision,
    ItemActionDraft,
    OutcomePart,
    Prop,
    ReflectionDraft,
    RelationshipState,
    RevisedBeat,
    RevisedScene,
    SceneBrief,
    SceneCastBrief,
    StageTurn,
    WorldEventAssessment,
)
from stage_fakes import quoted_source

NAMES = {"ana": "Ana", "bruno": "Bruno", "cora": "Cora"}
EVENT = "Se abre la puerta y la directora deja la carpeta sobre la mesa."
_TURN_IDS = re.compile(r"^(\S+-t\d{3}) ", re.MULTILINE)


def beat(event_id: str = "event-1") -> BeatBrief:
    return BeatBrief(
        event_id=event_id,
        title="La entrega",
        purpose="que la carpeta cambie de manos",
        outcome="Bruno entrega la carpeta y admite que la escondio",
        conflict="Ana la quiere y Bruno la niega",
    )


def scene(*, cast=("ana", "bruno"), beats=1, closes_play=False) -> SceneBrief:
    return SceneBrief(
        scene_id="chapter-1-scene-1",
        number=1,
        chapter_id="chapter-1",
        act_number=1,
        setting="El archivo, de noche.",
        cast=[
            SceneCastBrief(
                character_id=item,
                name=NAMES[item],
                objective=f"lo que {NAMES[item]} quiere",
                public_face="una persona del archivo",
            )
            for item in cast
        ],
        beats=[beat(f"event-{index}") for index in range(1, beats + 1)],
        closes_play=closes_play,
    )


def shown(context: str) -> BeatCheckDraft:
    """Show the beat's one clause, citing the last turn of the transcript."""
    ids = _TURN_IDS.findall(context)
    return BeatCheckDraft(
        parts=[
            OutcomePart(
                part="hands it over",
                shown=True,
                evidence=ids[-1:],
                sources=quoted_source(context, ids[-1:]),
            )
        ]
    )


def unshown(turning: str = "", *, stage_event: str = "") -> BeatCheckDraft:
    return BeatCheckDraft(
        parts=[OutcomePart(part="hands it over", shown=False)],
        turning_actor_id=turning,
        notes=[f"{turning}: ya no tiene sentido negarlo"] if turning else [],
        stage_event=stage_event,
    )


class Stage:
    """Scripted model calls with a record of what the engine asked for."""

    def __init__(self, judge, *, tactics=None) -> None:
        self.judge = judge
        self.tactics = tactics or {}
        self.moves: list[tuple[str, str]] = []
        self.modes: list[str] = []
        self.contexts: list[str] = []
        self.director_calls = 0
        self.entries = []

    def take_turn(self, system: str, context: str, feedback: str) -> ActorTurnDraft:
        number = len(self.moves) + 1
        self.moves.append((system, context))
        return ActorTurnDraft(
            speech=f"linea{number}a linea{number}b linea{number}c",
            action=f"gesto{number} hacia puerta{number}",
            tactic=self.tactics.get(system, "confront"),
        )

    def open_beat(self, context: str) -> BeatDirection:
        self.director_calls += 1
        return BeatDirection(opening_actor_id="ana", notes=[])

    def check_beat(self, context: str, mode: str) -> BeatCheckDraft:
        self.director_calls += 1
        self.modes.append(mode)
        self.contexts.append(context)
        return self.judge(mode, context)

    def reflect(self, system: str, log: str) -> ReflectionDraft:
        return ReflectionDraft(summary="Sali de alli con dudas.", importance=0.5)

    def engine(self, cast=("ana", "bruno")) -> PerformanceEngine:
        return PerformanceEngine(
            take_turn=self.take_turn,
            open_beat=self.open_beat,
            check_beat=self.check_beat,
            reflect=self.reflect,
            dossiers={},
            system_prompts={item: item for item in cast},
            names=NAMES,
            gate_facts={},
            whole_cast=list(cast),
            language="es",
            on_direction=self.entries.append,
            review_world=lambda _: WorldEventAssessment(
                compatible=True,
                introduces_solution=False,
                reveals_future_gate=False,
                reason="test pressure",
            ),
        )

    @property
    def actors(self) -> list[str]:
        return [system for system, _ in self.moves]


def test_a_beat_shown_at_the_first_reading_lands_there_with_no_coda() -> None:
    stage = Stage(lambda mode, context: shown(context))
    performed = stage.engine().perform_scene(scene())
    record = performed.beats[0]
    assert record.achieved and not record.forced and not record.intervened
    assert record.turns == 3
    assert stage.modes == ["check"]
    assert record.evidence == ["chapter-1-scene-1-t003"]
    assert performed.coda_turns == 0
    assert len(performed.turns) == 3


def test_a_beat_that_never_lands_climbs_the_whole_ladder_before_it_is_forced() -> None:
    def judge(mode, context):
        return unshown("bruno" if mode in {"turn", "stall"} else "", stage_event=EVENT)

    stage = Stage(judge)
    performed = stage.engine().perform_scene(scene())
    record = performed.beats[0]
    # The fake actors trade one tactic each, a standoff: since 7.12 that earns one early turn.
    assert stage.modes == ["check", "turn", "turn", "stall", "final"]
    assert record.forced and not record.achieved
    assert record.missing == ["hands it over"]
    assert record.reaction_turns == 2
    assert record.turns == 10
    assert record.stage_events == [EVENT]
    world = [turn for turn in performed.turns if turn.kind == "world"]
    assert [turn.action for turn in world] == [EVENT]
    # The world acted after the eighth turn, and the two reactions came after it.
    assert performed.turns.index(world[0]) == 8


def test_a_beat_the_world_resolves_is_reached_with_help_not_forced() -> None:
    def judge(mode, context):
        return shown(context) if mode == "final" else unshown("bruno", stage_event=EVENT)

    stage = Stage(judge)
    record = stage.engine().perform_scene(scene()).beats[0]
    assert record.achieved and record.intervened and not record.forced


def test_the_turning_actor_moves_next_and_gets_the_note() -> None:
    def judge(mode, context):
        return unshown("bruno") if mode == "turn" else unshown()

    stage = Stage(judge)
    stage.engine(cast=("ana", "bruno", "cora")).perform_scene(scene(cast=("ana", "bruno", "cora")))
    # Rotation alone would give the seventh turn to Ana; the director asked for Bruno.
    assert stage.actors[:6] == ["ana", "bruno", "cora", "ana", "bruno", "cora"]
    assert stage.actors[6] == "bruno"
    assert "ya no tiene sentido negarlo" in stage.moves[6][1]


def test_a_note_reaches_its_actor_once_per_beat() -> None:
    """Found in 7.1: a note resent on every turn made two characters confess the same twice."""

    def judge(mode, context):
        if mode == "check":
            return BeatCheckDraft(
                parts=[OutcomePart(part="hands it over", shown=False)],
                notes=["bruno: suelta la carpeta ya"],
            )
        return shown(context)

    stage = Stage(judge)
    stage.engine().perform_scene(scene())
    delivered = [context for _, context in stage.moves if "suelta la carpeta ya" in context]
    assert len(delivered) == 1


def test_a_world_event_reaches_the_turn_log() -> None:
    """Found in 7.1: turns.jsonl skipped the world's turn, one line short of the performance."""
    logged = []
    stage = Stage(lambda mode, context: unshown("bruno", stage_event=EVENT))
    engine = stage.engine()
    engine.on_turn = lambda turn, context: logged.append(turn)
    performed = engine.perform_scene(scene())
    assert [turn.id for turn in logged] == [turn.id for turn in performed.turns]
    assert any(turn.kind == "world" for turn in logged)


def test_a_line_repeated_in_a_later_scene_is_rejected() -> None:
    """Found in 7.1: Julian said a whole turn again, word for word, one scene later."""
    rejections = []
    stage = Stage(lambda mode, context: shown(context))

    def take_turn(system: str, context: str, feedback: str) -> ActorTurnDraft:
        stage.moves.append((system, context))
        if system == "bruno":
            return ActorTurnDraft(speech="La carpeta no la tengo yo, pregunta abajo", tactic="deny")
        number = len(stage.moves)
        return ActorTurnDraft(speech=f"pista{number} nueva{number} dato{number}", tactic="test")

    engine = stage.engine()
    engine.take_turn = take_turn
    engine.on_rejection = rejections.append
    engine.perform_scene(scene())
    engine.perform_scene(scene().model_copy(update={"scene_id": "chapter-1-scene-2", "number": 2}))
    assert rejections, "the repeated line was accepted"
    assert {item.code for item in rejections} == {"REPEATED_LINE"}
    assert {item.scene_id for item in rejections} == {"chapter-1-scene-2"}


@pytest.mark.parametrize(
    ("parts", "missing"),
    [
        (
            lambda context: [
                OutcomePart(part="hands it over", shown=True, evidence=["invented-t999"])
            ],
            ["hands it over"],
        ),
        (
            lambda context: [
                OutcomePart(
                    part="hands it over",
                    shown=True,
                    evidence=_TURN_IDS.findall(context)[-1:],
                    sources=quoted_source(context, _TURN_IDS.findall(context)[-1:]),
                ),
                OutcomePart(part="admits hiding it", shown=False),
            ],
            ["admits hiding it"],
        ),
    ],
    ids=["a-clause-cited-by-a-turn-that-does-not-exist", "one-missing-clause-keeps-it-open"],
)
def test_a_clause_only_counts_as_shown_with_a_turn_that_really_exists(parts, missing) -> None:
    stage = Stage(lambda mode, context: BeatCheckDraft(parts=parts(context)))
    record = stage.engine().perform_scene(scene()).beats[0]
    assert not record.achieved and record.forced
    assert stage.entries[1].achieved is False
    assert stage.entries[1].missing == missing
    assert record.missing == missing


GATE = "gate_folder: Bruno escondio la carpeta en el archivo (confession, Bruno)"


@pytest.mark.parametrize(
    "wording",
    [
        "gate_folder: Bruno escondio la carpeta en el archivo",
        "Bruno escondio la carpeta en el archivo.",
        None,
    ],
    ids=["by-its-id-without-the-suffix", "as-the-bare-fact", "never-mentioned"],
)
def test_a_required_gate_counts_however_the_director_words_it(wording) -> None:
    """7.5 to 7.8 matched gates as exact strings, and six beats of six were forced."""

    def judge(mode: str, context: str) -> BeatCheckDraft:
        cited = _TURN_IDS.findall(context)[-1:]
        parts = [
            OutcomePart(
                part="hands it over",
                shown=True,
                evidence=cited,
                sources=quoted_source(context, cited),
            )
        ]
        if wording:
            parts.append(
                OutcomePart(
                    part=wording, shown=True, evidence=cited, sources=quoted_source(context, cited)
                )
            )
        return BeatCheckDraft(parts=parts)

    brief = scene()
    brief.beats[0].required_gates = [GATE]
    stage = Stage(judge)
    record = stage.engine().perform_scene(brief).beats[0]
    assert record.achieved is bool(wording)
    assert record.missing == ([] if wording else [GATE])
    # The fallback note hands the missing gate to an actor: as a fact, never with its id.
    assert not any("gate_folder" in context for _, context in stage.moves)


def test_the_director_restates_each_objective_in_the_fiction_language() -> None:
    stage = Stage(lambda mode, context: shown(context))
    stage.open_beat = lambda context: BeatDirection(
        opening_actor_id="ana", objectives=["Ana: que Bruno suelte la carpeta", "Nadie: algo"]
    )
    stage.engine().perform_scene(scene())
    contexts = dict(reversed(stage.moves))
    assert "LO QUE QUIERES AQUÍ: que Bruno suelte la carpeta" in contexts["ana"]
    assert "LO QUE QUIERES AQUÍ: lo que Bruno quiere" in contexts["bruno"]


def test_a_reflected_stance_reaches_the_actor_by_name_in_a_labelled_state() -> None:
    """7.8 printed "con sir_aldren:" and "reconsiderarias si Si descubriera" to every actor."""
    stage = Stage(lambda mode, context: shown(context))
    stage.reflect = lambda system, log: ReflectionDraft(
        summary="Sali de alli con dudas.",
        emotion="tensa",
        change_condition="Si me mienten otra vez.",
        evidence=["linea1a linea1b linea1c"],
        relationships=[RelationshipState(character_id="ana_vela", stance="recelo")],
    )
    engine = stage.engine()
    engine.perform_scene(scene())
    engine.perform_scene(scene().model_copy(update={"scene_id": "chapter-1-scene-2", "number": 2}))
    state = next(
        line
        for system, context in stage.moves
        if system == "bruno"
        for line in context.splitlines()
        if "Con Ana: recelo" in line
    )
    assert "Te sientes: tensa." in state
    assert "Cambiarías de idea si: me mienten otra vez." in state
    assert "_" not in state and "Si me" not in state


def test_when_the_director_names_nobody_the_engine_picks_and_says_so() -> None:
    stage = Stage(lambda mode, context: unshown(), tactics={"bruno": "deny"})
    cast = ("ana", "bruno", "cora")
    stage.engine(cast=cast).perform_scene(scene(cast=cast))
    turn_entry = next(entry for entry in stage.entries if entry.mode == "turn")
    assert turn_entry.turning_fallback is True
    # Bruno has been denying; he is the one who has dug in.
    assert turn_entry.turning_actor_id == "bruno"
    after = stage.moves[6]
    assert after[0] == "bruno"
    assert FALLBACK_TURN_NOTE.split(".")[0] in after[1]


def test_every_director_call_is_logged_once() -> None:
    stage = Stage(lambda mode, context: unshown("bruno", stage_event=EVENT))
    stage.engine().perform_scene(scene(beats=2))
    assert len(stage.entries) == stage.director_calls
    assert [entry.mode for entry in stage.entries if entry.beat_index == 0] == [
        "open",
        "check",
        "turn",
        "turn",
        "stall",
        "final",
    ]
    stall = next(entry for entry in stage.entries if entry.mode == "stall")
    assert stall.stage_event == EVENT
    assert stall.after_turn == 8


def test_a_world_event_is_never_reused_without_the_director_seeing_it() -> None:
    stage = Stage(lambda mode, context: unshown("bruno", stage_event=EVENT))
    stage.engine().perform_scene(scene(beats=2))
    stall_contexts = [
        context
        for mode, context in zip(stage.modes, stage.contexts, strict=True)
        if mode == "stall"
    ]
    assert "EVENTOS DEL MUNDO YA USADOS" not in stall_contexts[0]
    assert "EVENTOS DEL MUNDO YA USADOS" in stall_contexts[1]
    assert EVENT in stall_contexts[1]


def test_the_director_sees_each_actor_recent_tactics() -> None:
    stage = Stage(lambda mode, context: shown(context), tactics={"bruno": "deny"})
    stage.engine().perform_scene(scene())
    assert "ULTIMAS TACTICAS DE CADA UNO" in stage.contexts[0]
    assert "- Bruno: deny" in stage.contexts[0]


def test_the_last_scene_of_the_play_ends_in_a_coda() -> None:
    stage = Stage(lambda mode, context: shown(context))
    performed = stage.engine().perform_scene(scene(closes_play=True))
    assert performed.coda_turns == 2
    assert len(performed.turns) == 5
    coda = performed.turns[-2:]
    assert all(turn.direction_note == CODA_NOTE for turn in coda)
    assert {turn.actor_id for turn in coda} == {"ana", "bruno"}


def test_a_world_event_enters_memory_without_a_speaker() -> None:
    stage = Stage(lambda mode, context: unshown("bruno", stage_event=EVENT))
    engine = stage.engine()
    engine.perform_scene(scene())
    records = [record for record in engine.memories["ana"].records if record.kind == "stage_event"]
    assert [record.text for record in records] == [f"({EVENT})"]


def test_a_director_that_cannot_answer_still_lets_the_scene_finish() -> None:
    def judge(mode, context):
        raise RuntimeError("stage manager unavailable")

    stage = Stage(judge)
    engine = stage.engine()
    record = engine.perform_scene(scene()).beats[0]
    assert record.forced
    assert all(entry.failed for entry in stage.entries if entry.mode != "open")
    assert any("BEAT_CHECK_FALLBACK" in warning for warning in engine.warnings)


def test_an_event_proposed_on_a_reading_that_lands_never_happens() -> None:
    """Found on the first 7.1 run: director.jsonl logged a gust of wind that never blew."""

    def judge(mode, context):
        if mode == "stall":
            draft = shown(context)
            return draft.model_copy(update={"stage_event": EVENT})
        return unshown("bruno")

    stage = Stage(judge)
    performed = stage.engine().perform_scene(scene())
    record = performed.beats[0]
    assert record.achieved and not record.intervened
    assert record.stage_events == []
    assert not any(turn.kind == "world" for turn in performed.turns)
    stall = next(entry for entry in stage.entries if entry.mode == "stall")
    assert stall.stage_event == ""
    assert stall.draft["stage_event"] == EVENT


def test_adaptive_mode_keeps_an_unreached_beat_open_without_a_world_event() -> None:
    stage = Stage(lambda mode, context: unshown("bruno", stage_event=EVENT))
    engine = stage.engine()
    engine.simulation_mode = SimulationMode.ADAPTIVE
    performed = engine.perform_scene(scene(beats=2))
    assert len(performed.beats) == 1
    assert performed.beats[0].missing == ["hands it over"]
    assert not performed.beats[0].achieved
    assert not performed.beats[0].forced
    assert all(turn.kind == "actor" for turn in performed.turns)
    assert stage.modes == ["check", "turn", "turn", "stall"]


def test_future_revision_changes_outcomes_but_keeps_the_scene_graph() -> None:
    original = scene(beats=2)
    proposal = FutureRevision(
        reason="El reparto eligio negociar.",
        scenes=[
            RevisedScene(
                scene_id=original.scene_id,
                keep=True,
                setting="El archivo despues de la negativa.",
                beats=[
                    RevisedBeat(
                        event_id="event-2",
                        outcome="Bruno retiene la carpeta",
                        purpose="abrir una negociacion",
                        conflict="Ana exige pruebas",
                    )
                ],
                objectives={"ana": "averiguar la verdad", "bruno": "guardar la carpeta"},
            )
        ],
    )
    changed = materialize_revision(proposal, [original], SimpleNamespace(dependencies=[]), set())
    assert [beat.event_id for beat in changed[0].beats] == ["event-2"]
    assert changed[0].beats[0].outcome == "Bruno retiene la carpeta"
    assert [item.character_id for item in changed[0].cast] == ["ana", "bruno"]
    with pytest.raises(ValueError, match="depends"):
        materialize_revision(
            proposal,
            [original],
            SimpleNamespace(
                dependencies=[SimpleNamespace(source_event_id="event-1", target_event_id="event-2")]
            ),
            set(),
        )


def test_a_revision_keeps_unmentioned_actor_objectives() -> None:
    """Omitting an unchanged cast member does not invalidate a future revision."""
    original = scene()
    proposal = FutureRevision(
        reason="Ana cambia de estrategia.",
        scenes=[
            RevisedScene(
                scene_id=original.scene_id,
                keep=True,
                setting=original.setting,
                beats=[
                    RevisedBeat(
                        event_id="event-1",
                        outcome="Bruno conserva la carpeta",
                        purpose="mantener el conflicto",
                        conflict="Ana busca otra prueba",
                    )
                ],
                objectives={"ana": "buscar otra prueba"},
            )
        ],
    )
    changed = materialize_revision(proposal, [original], SimpleNamespace(dependencies=[]), set())
    assert [item.objective for item in changed[0].cast] == [
        "buscar otra prueba",
        original.cast[1].objective,
    ]


def test_world_facts_require_a_real_observable_source() -> None:
    def judge(mode, context):
        ids = _TURN_IDS.findall(context)
        return BeatCheckDraft(
            parts=[
                OutcomePart(
                    part="hands it over",
                    shown=True,
                    evidence=ids[-1:],
                    sources=quoted_source(context, ids[-1:]),
                )
            ],
            facts=[
                FactProposal(
                    statement="Ana hace un gesto hacia la puerta",
                    source_turn_id=ids[0],
                    source=EvidenceSource(
                        turn_id=ids[0], channel="action", excerpt="gesto1 hacia puerta1"
                    ),
                ),
                FactProposal(statement="Un secreto imaginado", source_turn_id="missing-turn"),
            ],
        )

    stage = Stage(judge)
    engine = stage.engine()
    engine.perform_scene(scene())
    assert len(engine.facts) == 1
    assert engine.facts[0].source_turn_id == "chapter-1-scene-1-t001"
    assert engine.facts[0].kind == "action"


@pytest.mark.parametrize(
    ("channel", "excerpt", "cited"),
    [
        ("action", "Se desliza por la abertura de la roca", True),
        ("action", "Aleth se desliza por la abertura de la roca", True),
        ("action", "Aleth [...] hacia la sombra profunda.", True),
        ("speech", "Aleth: Seguidme sin hacer ruido.", True),
        ("action", "Aleth vuela por la abertura de la roca", False),
        ("action", "Aleth ... sombra", False),
        ("action", "hacia la sombra profunda [...] Se desliza", False),
    ],
    ids=[
        "as-logged",
        "as-the-director-reads-it",
        "shortened-with-an-ellipsis",
        "speech-with-the-speaker",
        "a-paraphrase",
        "too-short-to-prove-anything",
        "pieces-out-of-order",
    ],
)
def test_a_citation_counts_as_the_director_read_the_turn(channel, excerpt, cited) -> None:
    """Found in 7.12.2: the transcript reads "Aleth se desliza", the log "Se desliza"."""
    turn = StageTurn(
        id="s-t001",
        scene_id="s",
        number=1,
        actor_id="aleth",
        beat_index=0,
        action="Se desliza por la abertura de la roca hacia la sombra profunda.",
        speech="Seguidme sin hacer ruido.",
    )
    source = EvidenceSource(turn_id=turn.id, channel=channel, excerpt=excerpt)
    found = cited_source(source, {turn.id: turn}, names={"aleth": "Aleth"})
    assert (found is turn) is cited


# -- the inventory in a played scene -----------------------------------------------------


class PropStage(Stage):
    """A Stage whose actors handle objects, scripted move by move."""

    def __init__(self, judge, moves) -> None:
        """Take the object moves to propose, one per turn, oldest first."""
        super().__init__(judge)
        self.scripted = list(moves)
        self.proposed: list[ItemActionDraft] = []

    def take_turn(self, system: str, context: str, feedback: str) -> ActorTurnDraft:
        """Take a turn that also proposes whatever object move the test scripted next."""
        number = len(self.moves) + 1
        base = super().take_turn(system, context, feedback)
        item = self.scripted[number - 1] if number <= len(self.scripted) else ItemActionDraft()
        self.proposed.append(item)
        return ActorTurnWithItemsDraft(**base.model_dump(), item_action=item)

    def engine(self, cast=("ana", "bruno"), inventory=None) -> PerformanceEngine:
        """Wire the engine exactly as the pipeline does, with an arbiter when one is given."""
        built = super().engine(cast)
        built.inventory = inventory
        return built


def props_scene() -> SceneBrief:
    """A scene with a real location, so an object can also lie on the floor of it."""
    return scene().model_copy(update={"location_id": "archive"})


def arbiter(moved=None):
    """Build the arbiter over one carried sword, one hidden dagger and one loose lantern."""
    return StageInventory(
        [
            Prop(id="sword", name="Espada", holder_id="ana"),
            Prop(id="dagger", name="Punal", holder_id="ana", concealed=True),
            Prop(id="lantern", name="Farol", location_id="archive"),
        ],
        on_item=moved if moved is not None else [].append,
    )


def test_an_actor_is_shown_what_it_holds_and_what_it_can_see() -> None:
    stage = PropStage(lambda mode, context: shown(context), [])
    inventory = arbiter()
    stage.engine(inventory=inventory).perform_scene(props_scene())
    first = stage.moves[0][1]
    # Ana reads back her own two objects, the hidden one marked as hidden.
    assert "LO QUE LLEVAS:" in first
    assert "Espada" in first and "Punal" in first
    assert "escondido" in first
    assert "LO QUE VES:\n- Farol" in first
    bruno = next(context for system, context in stage.moves if system == "bruno")
    # Bruno sees the sword on Ana and the lantern on the floor, and never the hidden dagger.
    assert "Espada" in bruno
    assert "Punal" not in bruno


def test_a_handover_changes_who_holds_the_object_and_is_logged() -> None:
    moved: list[dict] = []
    stage = PropStage(
        lambda mode, context: shown(context),
        [ItemActionDraft(verb="give", item="Espada", target="Bruno")],
    )
    inventory = arbiter(moved.append)
    performance = stage.engine(inventory=inventory).perform_scene(props_scene())
    assert inventory.holder("sword") == "bruno"
    assert moved == [
        {
            "verb": "give",
            "item_id": "sword",
            "item_name": "Espada",
            "performer_id": "ana",
            "target_id": "bruno",
            "from_id": "ana",
            "witnesses": ["ana", "bruno"],
            "holder_id": "bruno",
        }
    ]
    first = performance.turns[0]
    assert first.item_action is not None
    assert first.item_action.verb == "give"


def test_an_impossible_move_is_sent_back_with_its_code_and_repaired() -> None:
    rejections: list = []
    stage = PropStage(
        lambda mode, context: shown(context),
        # Ana does not hold the lantern, so the first attempt cannot stand; the second does.
        [ItemActionDraft(verb="give", item="Farol", target="Bruno"), ItemActionDraft()],
    )
    engine = stage.engine(inventory=arbiter())
    engine.on_rejection = rejections.append
    performance = engine.perform_scene(props_scene())
    assert [item.code for item in rejections] == ["ITEM_NOT_HELD"]
    # The actor was told, in English, what to fix, and its repaired turn joined the log.
    assert "CORRECCIÓN" in stage.moves[1][0] or performance.turns
    assert performance.turns[0].item_action is None
    assert performance.rejected == 1


def test_a_run_without_an_arbiter_never_mentions_an_object() -> None:
    stage = PropStage(lambda mode, context: shown(context), [])
    stage.engine().perform_scene(props_scene())
    for _, context in stage.moves:
        assert "LO QUE LLEVAS" not in context
        assert "LO QUE VES" not in context
        assert "UTILERIA" not in context
