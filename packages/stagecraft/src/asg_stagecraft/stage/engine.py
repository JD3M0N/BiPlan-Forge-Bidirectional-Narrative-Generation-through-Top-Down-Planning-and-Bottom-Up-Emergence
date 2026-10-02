"""The scene engine: runs one scene of the performance, turn by turn.

The engine owns no model calls of its own. Every one it needs - take a turn, open a beat, check
a beat, reflect - arrives as a callable, so a scene can be played end to end in a test with
canned responses and no provider at all. What the engine owns is the part that must be the same
on every run: the order of turns, who perceived what, what each memory holds, and when a beat is
declared reached, reached with help, or forced.

The loop, in full:

    open the beat  ->  the named actor moves
    a turn arrives ->  validate it, repair once, or skip it
    it is accepted ->  work out who witnessed it, write it into exactly those memories
    every third turn, ask the director to read the beat clause by clause
    every clause shown, with a turn to prove it  ->  the beat lands
    the second reading still short  ->  the director names who has to change, and why
    the budget runs out  ->  the world delivers the missing clause, two actors react, a last
                            reading decides between "reached with help" and "forced"
    the play's last scene  ->  a short coda, so the story ends in a scene
    the scene ends ->  every actor reflects, and their state is replaced rather than appended

The escalation exists because the first real runs deadlocked: one character pressed, another
resisted, nobody ever had a reason to cross, and a thunderclap closed four beats in twelve
without resolving them - one of them the ending of a mystery.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..formats import ActorMemory, SimulationMode
from ..runtime.errors import NON_DEGRADABLE_ERRORS, StagePerformanceError
from . import policy
from .inventory import StageInventory
from .memory import CharacterMemory
from .perception import item_line, stage_direction, witnesses
from .render import actor_turn_context, director_beat_context, scene_log
from .schemas import (
    ActorDossier,
    ActorTurnDraft,
    BeatBrief,
    BeatCheckDraft,
    BeatDirection,
    BeatEvidence,
    BeatRecord,
    CharacterState,
    DirectorEntry,
    ItemAction,
    ItemActionDraft,
    ReflectionDraft,
    SceneBrief,
    ScenePerformance,
    StageFact,
    StageTurn,
    TurnRejection,
)
from .validation import TurnIssue, normalize_turn, validate_turn

# One repair attempt per turn. A second one costs as much as a turn and rarely lands: the actor
# that produced an empty or repeated turn twice is better skipped than argued with.
TURN_ATTEMPTS = 2
# How many consecutive actor failures mean the provider, not the prompt, is the problem.
CONSECUTIVE_FAILURE_LIMIT = 4
# Turns the actors get to answer the world's intervention before the beat is read one last time.
REACTION_TURNS = 2
# Turns the play's last scene keeps after its last beat, so the story ends on a scene.
CODA_TURNS = 2
# How many of each actor's recent tactics the director sees when it has to spot a deadlock.
TACTIC_WINDOW = 3
# Tactics that dig in rather than move. The deterministic fallback for naming who must change
# picks whoever has been using them most.
RESISTING_TACTICS = frozenset({"deny", "deflect", "lie", "stall", "withdraw"})

CODA_NOTE = (
    "The matter is settled now. Play what it has cost you, or what it leaves you with, "
    "in one last move."
)
# Used only when the director was asked to name who must change and did not.
FALLBACK_TURN_NOTE = (
    "The ground has shifted under you. What has to happen now: {part}. Let your character be "
    "the one who makes it happen, for their own reasons."
)


@dataclass
class _Verdict:
    """What the engine made of one director reading: derived, never declared by the model."""

    achieved: bool
    evidence: list[str] = field(default_factory=list)
    proofs: list[BeatEvidence] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    turning_actor_id: str = ""
    turning_fallback: bool = False
    next_actor_id: str = ""
    notes: list[str] = field(default_factory=list)
    stage_event: str = ""


@dataclass
class _SceneRun:
    """The mutable state of one scene while it is being played."""

    brief: SceneBrief
    on_stage: list[str]
    objectives: dict[str, str]
    turns: list[StageTurn] = field(default_factory=list)
    rejected: int = 0
    skipped: int = 0


class PerformanceEngine:
    """Run scenes of the performance against injected model calls."""

    def __init__(
        self,
        *,
        take_turn: Callable[[str, str, str], ActorTurnDraft],
        open_beat: Callable[[str], BeatDirection],
        check_beat: Callable[[str, str], BeatCheckDraft],
        reflect: Callable[[str, str], ReflectionDraft],
        dossiers: dict[str, ActorDossier],
        system_prompts: dict[str, str],
        names: dict[str, str],
        gate_facts: dict[str, list[str]],
        whole_cast: list[str],
        language: str,
        actor_memory: ActorMemory = ActorMemory.OWN,
        simulation_mode: SimulationMode = SimulationMode.FIXED,
        inventory: StageInventory | None = None,
        turns_per_beat: int = 8,
        reaction_turns: int = REACTION_TURNS,
        coda_turns: int = CODA_TURNS,
        on_event: Callable[[str, str], None] | None = None,
        on_rejection: Callable[[TurnRejection], None] | None = None,
        on_turn: Callable[[StageTurn, str], None] | None = None,
        on_direction: Callable[[DirectorEntry], None] | None = None,
        on_attempt: Callable[[dict], None] | None = None,
        on_reflection: Callable[[dict], None] | None = None,
        on_decision: Callable[[str], None] | None = None,
        on_director_request: Callable[[dict], None] | None = None,
        on_fact: Callable[[StageFact], None] | None = None,
    ) -> None:
        """Wire the engine to its model calls and the cast it will run."""
        self.take_turn = take_turn
        self.open_beat = open_beat
        self.check_beat = check_beat
        self.reflect = reflect
        self.dossiers = dossiers
        self.system_prompts = system_prompts
        self.names = names
        self.gate_facts = gate_facts
        self.whole_cast = whole_cast
        self.language = language
        self.actor_memory = actor_memory
        self.simulation_mode = simulation_mode
        # None in every run without the inventory option, and then no object block, no object
        # schema and no arbitration: the performance is byte for byte the one 7.5 produced.
        self.inventory = inventory
        self.on_attempt = on_attempt
        self.on_reflection = on_reflection
        self.on_decision = on_decision
        self.on_director_request = on_director_request
        self.on_fact = on_fact
        self.facts: list[StageFact] = []
        self._clauses: dict[str, list[str]] = {}
        self.turns_per_beat = turns_per_beat
        self.reaction_turns = reaction_turns
        self.coda_turns = coda_turns
        self.on_event = on_event
        self.on_rejection = on_rejection
        self.on_turn = on_turn
        self.on_direction = on_direction
        self.memories: dict[str, CharacterMemory] = {
            character_id: CharacterMemory(character_id) for character_id in whole_cast
        }
        self.states: dict[str, CharacterState] = {
            character_id: CharacterState(
                character_id=character_id,
                scene_number=0,
                goal=dossier.initial_goal or dossier.want,
                commitment=dossier.want,
            )
            for character_id, dossier in dossiers.items()
        }
        self.warnings: list[str] = []
        # World events already used anywhere in the play, so the director never reaches for the
        # same device twice: the first real run used three thunderclaps and a power cut.
        self.used_events: list[str] = []
        # Everything each actor has said and done in the play, across scenes, so a line repeated
        # a scene later is caught like one repeated a turn later. 7.1 let one through verbatim.
        self._spoken: dict[str, list[str]] = {}
        self._gestures: dict[str, list[str]] = {}
        # How each character left every scene, in order: the emotion its reflection named.
        self.emotions: dict[str, list[str]] = {}
        self._failures = 0
        self._seed_initial_knowledge()

    def perform_scene(self, scene: SceneBrief) -> ScenePerformance:
        """Play one scene to the end of its last beat and return what was performed."""
        run = _SceneRun(
            brief=scene,
            on_stage=[member.character_id for member in scene.cast],
            objectives={member.character_id: member.objective for member in scene.cast},
        )
        beats = []
        for index, beat in enumerate(scene.beats):
            result = self._perform_beat(run, index, beat)
            beats.append(result)
            if self.simulation_mode is SimulationMode.ADAPTIVE and not result.achieved:
                break
        self._scene_beats = beats
        coda = self._play_coda(run) if scene.closes_play else 0

        if not run.turns:
            error = StagePerformanceError(
                "Una escena no produjo ni un solo turno valido.",
                details={"scene_id": scene.scene_id, "chapter_id": scene.chapter_id},
                recommendations=[f"Revisa los turnos rechazados en stage/{scene.scene_id}/."],
            )
            error.stage = "performance"
            raise error

        self._reflect_all(scene, run.turns, run.on_stage)
        return ScenePerformance(
            scene_id=scene.scene_id,
            number=scene.number,
            chapter_id=scene.chapter_id,
            turns=run.turns,
            beats=beats,
            rejected=run.rejected,
            skipped=run.skipped,
            coda_turns=coda,
        )

    def _announce_decision(self, decision_id: str) -> None:
        """Publish the decision currently responsible for a model call."""
        if self.on_decision:
            self.on_decision(decision_id)

    def perform_open_coda(self, brief: SceneBrief, performed: ScenePerformance) -> ScenePerformance:
        """Give an unexpectedly final scene a short, explicitly open ending."""
        run = _SceneRun(
            brief=brief,
            on_stage=[member.character_id for member in brief.cast],
            objectives={member.character_id: member.objective for member in brief.cast},
            turns=list(performed.turns),
            rejected=performed.rejected,
            skipped=performed.skipped,
        )
        self._scene_beats = performed.beats
        count = self._play_coda(run, open_ending=True)
        if count:
            self._reflect_all(brief, run.turns, run.on_stage)
        return performed.model_copy(
            update={
                "turns": run.turns,
                "coda_turns": performed.coda_turns + count,
                "rejected": run.rejected,
                "skipped": run.skipped,
            }
        )

    # -- beats ---------------------------------------------------------------------------

    def _perform_beat(self, run: _SceneRun, index: int, beat: BeatBrief) -> BeatRecord:
        """Play one beat up the escalation ladder until it lands or is forced."""
        record = BeatRecord(event_id=beat.event_id, index=index)
        direction = self._open(run, index, beat)
        record.opening_actor_id = direction.opening_actor_id
        record.notes = list(direction.notes)
        requested, notes = direction.opening_actor_id, list(direction.notes)
        turns_in_beat = checks = 0

        while True:
            moved = self._advance(run, index, beat, requested, notes)
            notes = self._consume(notes, moved)
            requested = ""
            turns_in_beat += 1
            record.turns += 1
            at_cap = policy.must_force(turns_in_beat, turns_per_beat=self.turns_per_beat)
            if not at_cap and not policy.should_check(turns_in_beat):
                continue
            checks += 1
            mode = "stall" if at_cap else ("turn" if checks >= 2 else "check")
            verdict = self._check(run, index, beat, mode)
            record.checks += 1
            if verdict.turning_actor_id:
                record.turning_actor_id = verdict.turning_actor_id
            if verdict.achieved:
                self._land(record, verdict, run)
                return record
            if at_cap:
                if self.simulation_mode is SimulationMode.ADAPTIVE:
                    record.missing = list(verdict.missing)
                    self._emit("beat_unreached", f"{run.brief.scene_id} no alcanzo {beat.event_id}")
                else:
                    self._resolve_stall(run, index, beat, record, verdict)
                return record
            requested = verdict.turning_actor_id or verdict.next_actor_id
            notes = verdict.notes

    def _resolve_stall(
        self,
        run: _SceneRun,
        index: int,
        beat: BeatBrief,
        record: BeatRecord,
        verdict: _Verdict,
    ) -> None:
        """Let the world deliver what is missing, let the actors answer it, and read once more."""
        if verdict.stage_event:
            record.stage_events.append(verdict.stage_event)
            self.used_events.append(verdict.stage_event)
            event_turn = self._stage_event_turn(run, index, beat, verdict.stage_event)
            run.turns.append(event_turn)
            self._record_turn(event_turn, run.brief.number)
            # The world's turn belongs in the turn log like any other: 7.1 wrote one turn fewer
            # to turns.jsonl than the performance counted, for every event the world supplied.
            if self.on_turn:
                self.on_turn(event_turn, "")
        first = verdict.turning_actor_id if verdict.turning_actor_id in run.on_stage else ""
        notes = list(verdict.notes)
        for position in range(self.reaction_turns):
            moved = self._advance(run, index, beat, first if position == 0 else "", notes)
            notes = self._consume(notes, moved)
            record.reaction_turns += 1
            record.turns += 1
        final = self._check(run, index, beat, "final")
        record.checks += 1
        if final.achieved:
            record.intervened = True
            self._land(record, final, run)
            return
        record.forced = True
        record.missing = list(final.missing)
        record.evidence = list(final.evidence)
        record.proofs = list(final.proofs)
        self.warnings.append(
            f"[BEAT_FORCED] {run.brief.scene_id}: el beat {beat.event_id} no se alcanzo "
            f"ni con la intervencion del mundo."
        )
        self._emit("beat_forced", f"{run.brief.scene_id} forzo {beat.event_id}")

    def _land(self, record: BeatRecord, verdict: _Verdict, run: _SceneRun) -> None:
        """Close one beat as reached, keeping the turns that prove it."""
        record.achieved = True
        record.evidence = list(verdict.evidence)
        record.proofs = list(verdict.proofs)
        self._emit("beat_achieved", f"{run.brief.scene_id} alcanzo {record.event_id}")

    def _play_coda(self, run: _SceneRun, *, open_ending: bool = False) -> int:
        """Give the play's ending a scene: the most involved characters answer the outcome."""
        if not run.turns or self.coda_turns <= 0:
            return 0
        index = self._scene_beats[-1].index if self._scene_beats else len(run.brief.beats) - 1
        beat = run.brief.beats[index]
        tally = {
            actor: sum(1 for turn in run.turns if turn.actor_id == actor and turn.kind == "actor")
            for actor in run.on_stage
        }
        involved = sorted(
            run.on_stage, key=lambda actor: (-tally[actor], run.on_stage.index(actor))
        )
        chosen = involved[: self.coda_turns]
        # Whoever moved last cannot move again at once, so they close the coda instead.
        last = next((turn.actor_id for turn in reversed(run.turns) if turn.kind == "actor"), "")
        chosen.sort(key=lambda actor: actor == last)
        settled = (
            not open_ending
            and bool(self._scene_beats)
            and self._scene_beats[-1].event_id == run.brief.beats[-1].event_id
            and self._scene_beats[-1].achieved
        )
        note = (
            CODA_NOTE
            if settled
            else "La cuesti?n sigue abierta. Act?a seg?n lo que sabes y quieres ahora."
        )
        notes = [f"{actor}: {note}" for actor in chosen]
        played = 0
        for actor in chosen:
            moved = self._advance(run, index, beat, actor, notes)
            notes = self._consume(notes, moved)
            played += 1
        return played

    # -- turns ---------------------------------------------------------------------------

    def _advance(
        self,
        run: _SceneRun,
        index: int,
        beat: BeatBrief,
        requested: str,
        notes: list[str],
    ) -> str:
        """Play the next turn of the scene, recording it or counting it as skipped.

        Returns who was given the turn, so the caller can retire the note that actor just got.
        """
        actor_id = policy.next_actor(on_stage=run.on_stage, turns=run.turns, requested=requested)
        turn, failures = self._play_turn(
            scene=run.brief,
            beat_index=index,
            beat=beat,
            actor_id=actor_id,
            objective=run.objectives.get(actor_id, ""),
            note=self._note_for(notes, actor_id),
            on_stage=run.on_stage,
            turns=run.turns,
            number=len(run.turns) + 1,
        )
        run.rejected += failures
        if turn is None:
            run.skipped += 1
            self.warnings.append(
                f"[STAGE_TURN_SKIPPED] {run.brief.scene_id}: "
                f"{self.names.get(actor_id, actor_id)} no produjo un turno valido."
            )
            return actor_id
        run.turns.append(turn)
        # Applied before the turn is remembered, so what each witness records is the world as it
        # stands after the object moved, never before.
        if self.inventory is not None and turn.item_action is not None:
            self.inventory.apply(
                turn.item_action, actor_id=actor_id, location_id=run.brief.location_id or ""
            )
        self._record_turn(turn, run.brief.number)
        updates = {
            field: value
            for field, value in (
                ("goal", turn.goal_after),
                ("commitment", turn.commitment_after),
                ("cover_story", turn.cover_story_after),
                ("change_condition", turn.change_condition_after),
            )
            if value
        }
        if updates:
            previous = self.states.get(actor_id) or CharacterState(
                character_id=actor_id, scene_number=0
            )
            self.states[actor_id] = previous.model_copy(
                update={**updates, "scene_number": run.brief.number, "source_turn_id": turn.id}
            )
            if self.on_reflection:
                self.on_reflection(
                    {
                        "status": "state_updated",
                        "character_id": actor_id,
                        "source_turn_id": turn.id,
                        "state": self.states[actor_id].model_dump(mode="json"),
                    }
                )
        if turn.speech:
            self._spoken.setdefault(actor_id, []).append(turn.speech)
        if turn.action:
            self._gestures.setdefault(actor_id, []).append(turn.action)
        return actor_id

    @staticmethod
    def _consume(notes: list[str], actor_id: str) -> list[str]:
        """Retire the note an actor has just been given, so it is delivered once, not every turn.

        In 7.1 a note stayed live until the director's next reading, and two characters
        confessed the same thing twice because they were told to twice.
        """
        for position, note in enumerate(notes):
            head, _, body = note.partition(":")
            if head.strip().casefold() == actor_id.casefold() and body.strip():
                return [*notes[:position], *notes[position + 1 :]]
        return notes

    def _play_turn(
        self,
        *,
        scene: SceneBrief,
        beat_index: int,
        beat: BeatBrief,
        actor_id: str,
        objective: str,
        note: str,
        on_stage: list[str],
        turns: list[StageTurn],
        number: int,
    ) -> tuple[StageTurn | None, int]:
        """Take one actor's turn, repairing once, and return it with how often it was rejected."""
        memory = self.memories[actor_id]
        witnessed = [turn for turn in turns if actor_id in set(turn.witnesses)]
        recalled = memory.recall(
            self._query(scene, objective, witnessed),
            scene_number=scene.number,
            turn_number=number,
            present=[item for item in on_stage if item != actor_id],
        )
        context = actor_turn_context(
            scene=scene,
            objective=objective,
            state=self.states.get(actor_id),
            note=note,
            gate_facts=self.gate_facts.get(actor_id, []),
            memories=recalled,
            witnessed=witnessed,
            character_id=actor_id,
            names=self.names,
            held=self.inventory.held_by(actor_id) if self.inventory else None,
            in_reach=(
                self.inventory.in_reach(actor_id, on_stage, scene.location_id or "")
                if self.inventory
                else None
            ),
        )
        previous_speech = self._spoken.get(actor_id, [])
        previous_actions = self._gestures.get(actor_id, [])
        feedback = ""
        rejections = 0
        for attempt in range(1, TURN_ATTEMPTS + 1):
            attempt_id = f"{scene.scene_id}:{actor_id}:{number}:{attempt}"
            self._announce_decision(attempt_id)
            if self.on_attempt:
                self.on_attempt(
                    {
                        "id": attempt_id,
                        "status": "requested",
                        "scene_id": scene.scene_id,
                        "actor_id": actor_id,
                        "context": context,
                        "system_instruction": self.system_prompts[actor_id],
                        "feedback": feedback,
                    }
                )
            try:
                draft = self.take_turn(self.system_prompts[actor_id], context, feedback)
            except NON_DEGRADABLE_ERRORS as exc:
                if self.on_attempt:
                    self.on_attempt(
                        {"id": attempt_id, "status": "failed", "error": type(exc).__name__}
                    )
                raise
            except Exception as exc:
                rejections += 1
                self._reject(
                    scene, actor_id, attempt, "ACTOR_CALL_FAILED", type(exc).__name__, None
                )
                if self.on_attempt:
                    self.on_attempt(
                        {"id": attempt_id, "status": "failed", "error": type(exc).__name__}
                    )
                self._note_failure(actor_id)
                feedback = (
                    "\n\nCORRECCION: el intento anterior no pudo completarse. Vuelve a hacer tu "
                    "movimiento, mas corto y directo."
                )
                continue
            self._failures = 0
            if self.on_attempt:
                self.on_attempt(
                    {"id": attempt_id, "status": "proposed", "draft": draft.model_dump(mode="json")}
                )
            candidate = normalize_turn(
                draft,
                on_stage=on_stage,
                actor_name=self.names.get(actor_id, ""),
                names=self.names,
            )
            item_action = None
            try:
                validate_turn(
                    candidate, previous_speech=previous_speech, previous_actions=previous_actions
                )
                item_action = self._arbitrate(candidate, actor_id, scene, on_stage)
            except TurnIssue as issue:
                rejections += 1
                self._reject(
                    scene,
                    actor_id,
                    attempt,
                    issue.code,
                    str(issue),
                    candidate.model_dump(mode="json"),
                )
                if self.on_attempt:
                    self.on_attempt(
                        {
                            "id": attempt_id,
                            "status": "rejected",
                            "code": issue.code,
                            "normalized": candidate.model_dump(mode="json"),
                        }
                    )
                feedback = f"\n\nCORRECCION:\n{issue}\nVuelve a hacer tu movimiento."
                continue
            turn = StageTurn(
                **candidate.model_dump(exclude={"item_action"}),
                item_action=item_action,
                id=f"{scene.scene_id}-t{number:03d}",
                scene_id=scene.scene_id,
                number=number,
                actor_id=actor_id,
                beat_index=beat_index,
                beat_event_id=beat.event_id,
                witnesses=witnesses(
                    candidate,
                    actor_id=actor_id,
                    on_stage=on_stage,
                    whole_cast=self.whole_cast,
                    memory=self.actor_memory,
                ),
                direction_note=note,
                retrieved_memory_ids=[item.id for item in recalled],
                attempts=attempt,
            )
            if self.on_attempt:
                self.on_attempt(
                    {
                        "id": attempt_id,
                        "status": "accepted",
                        "turn_id": turn.id,
                        "normalized": candidate.model_dump(mode="json"),
                    }
                )
            if self.on_turn:
                self.on_turn(turn, context)
            return turn, rejections
        return None, rejections

    def _arbitrate(
        self,
        candidate: ActorTurnDraft,
        actor_id: str,
        scene: SceneBrief,
        on_stage: list[str],
    ) -> ItemAction | None:
        """Put the object move a turn proposed to the arbiter, if there is one to put.

        Called once the turn itself has validated, so a rejected object move costs the actor the
        same single repair any other fault would, with the arbiter's own English message.
        """
        if self.inventory is None:
            return None
        return self.inventory.resolve(
            getattr(candidate, "item_action", None) or ItemActionDraft(),
            actor_id=actor_id,
            on_stage=on_stage,
            location_id=scene.location_id or "",
            names=self.names,
            visibility=candidate.visibility,
            addressed_to=candidate.addressed_to,
            whole_cast=self.whole_cast,
        )

    def _stage_event_turn(
        self, run: _SceneRun, beat_index: int, beat: BeatBrief, text: str
    ) -> StageTurn:
        """Turn the director's intervention into something that happened on stage, for everyone.

        It enters the log as a turn so the narrator reads it exactly like anything else the
        scene produced - the log stays the single source of the story - but it is marked as the
        world's doing, because attributing a thunderclap to whoever happened to be on stage
        first would put words in a character's body.
        """
        number = len(run.turns) + 1
        return StageTurn(
            action=text,
            visibility="public",
            kind="world",
            tactic="",
            id=f"{run.brief.scene_id}-t{number:03d}",
            scene_id=run.brief.scene_id,
            number=number,
            actor_id=run.on_stage[0],
            beat_index=beat_index,
            beat_event_id=beat.event_id,
            witnesses=list(run.on_stage),
            direction_note="stage_event",
        )

    # -- the director --------------------------------------------------------------------

    def _open(self, run: _SceneRun, index: int, beat: BeatBrief) -> BeatDirection:
        """Ask the director to open one beat, falling back to a silent opening."""
        context = self._director_context(run, beat)
        decision_id = f"{run.brief.scene_id}:director:open:{len(run.turns)}"
        if self.on_decision:
            self.on_decision(decision_id)
        if self.on_director_request:
            self.on_director_request(
                {"decision_id": decision_id, "status": "requested", "context": context}
            )
        try:
            direction = self.open_beat(context)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception:
            self.warnings.append(
                f"[DIRECTION_FALLBACK] {run.brief.scene_id}: el beat {beat.event_id} "
                "se abrio sin nota."
            )
            self._log(run, index, beat, "open", None, None, failed=True)
            return BeatDirection(opening_actor_id=run.on_stage[0], notes=[])
        self._log(run, index, beat, "open", direction.model_dump(mode="json"), None)
        return direction

    def _check(self, run: _SceneRun, index: int, beat: BeatBrief, mode: str) -> _Verdict:
        """Ask the director to read the beat, and derive the verdict from its clauses."""
        context = self._director_context(run, beat)
        decision_id = f"{run.brief.scene_id}:director:{mode}:{len(run.turns)}"
        if self.on_decision:
            self.on_decision(decision_id)
        if self.on_director_request:
            self.on_director_request(
                {"decision_id": decision_id, "status": "requested", "context": context}
            )
        try:
            draft = self.check_beat(context, mode)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception:
            self.warnings.append(
                f"[BEAT_CHECK_FALLBACK] {run.brief.scene_id}: no se pudo comprobar {beat.event_id}."
            )
            verdict = _Verdict(achieved=False, missing=[beat.outcome])
            self._log(run, index, beat, mode, None, verdict, failed=True)
            return verdict
        verdict = self._derive(draft, run, mode, beat.event_id)
        self._accept_facts(draft, run)
        self._log(run, index, beat, mode, draft.model_dump(mode="json"), verdict)
        return verdict

    def _derive(self, draft: BeatCheckDraft, run: _SceneRun, mode: str, event_id: str) -> _Verdict:
        """Turn the director's clauses into a verdict the model never gets to declare.

        A clause counts as shown only when it cites a turn that exists. Every missing clause
        keeps the beat open. When the rung requires someone to be named and the director named
        nobody, or gave them no note, the engine fills the gap deterministically and says so.
        """
        known = {turn.id: turn for turn in run.turns}
        beat_key = run.brief.scene_id + ":" + event_id
        clauses = [part.part for part in draft.parts]
        required = run.brief.beats[
            next(index for index, beat in enumerate(run.brief.beats) if beat.event_id == event_id)
        ].required_gates
        frozen = self._clauses.setdefault(beat_key, list(dict.fromkeys([*clauses, *required])))
        evidence: list[str] = []
        proofs: list[BeatEvidence] = []
        missing: list[str] = []
        for part in draft.parts:
            if part.part not in frozen:
                continue
            cited = [
                item
                for item in part.evidence
                if item in known
                and (known[item].kind == "world" or known[item].action or known[item].speech)
            ]
            if part.shown and cited:
                evidence.extend(item for item in cited if item not in evidence)
                for item in cited:
                    turn = known[item]
                    kind = (
                        "world_event"
                        if turn.kind == "world"
                        else "action"
                        if turn.action
                        else "declaration"
                    )
                    proofs.append(
                        BeatEvidence(
                            clause_id=f"{event_id}:c{frozen.index(part.part) + 1:02d}",
                            turn_id=item,
                            kind=kind,
                            excerpt=turn.action if kind != "declaration" else turn.speech,
                        )
                    )
            else:
                missing.append(part.part)
        missing.extend(part for part in frozen if part not in clauses)
        achieved = bool(frozen) and not missing and set(clauses) == set(frozen)
        turning = draft.turning_actor_id if draft.turning_actor_id in run.on_stage else ""
        notes = list(draft.notes)
        fallback = False
        if not achieved and mode in {"turn", "stall"}:
            if not turning:
                turning = self._likely_turner(run)
                fallback = True
            if missing and not self._note_for(notes, turning):
                notes = [*notes[:1], f"{turning}: {FALLBACK_TURN_NOTE.format(part=missing[0])}"]
                fallback = True
        next_actor = draft.next_actor_id if draft.next_actor_id in run.on_stage else ""
        return _Verdict(
            achieved=achieved,
            evidence=sorted(evidence),
            proofs=proofs,
            missing=missing,
            turning_actor_id=turning if not achieved else "",
            turning_fallback=fallback,
            next_actor_id=next_actor,
            notes=notes,
            # A beat that lands on the stall reading needs no intervention, so the event the
            # director proposed never happens and must not be logged as if it had.
            stage_event=draft.stage_event.strip() if mode == "stall" and not achieved else "",
        )

    def _accept_facts(self, draft: BeatCheckDraft, run: _SceneRun) -> None:
        """Record only world changes grounded in a witnessed action or world turn."""
        turns = {turn.id: turn for turn in run.turns}
        previous = {fact.id for fact in self.facts}
        seen = {(fact.source_turn_id, fact.statement.casefold()) for fact in self.facts}
        for proposal in draft.facts:
            turn = turns.get(proposal.source_turn_id)
            if turn is None or not turn.action:
                continue
            if proposal.supersedes_id and proposal.supersedes_id not in previous:
                continue
            key = (turn.id, proposal.statement.casefold())
            if key in seen:
                continue
            fact = StageFact(
                id=f"fact-{len(self.facts) + 1:04d}",
                statement=proposal.statement,
                source_turn_id=turn.id,
                kind="world_event" if turn.kind == "world" else "action",
                witnesses=list(turn.witnesses),
                supersedes_id=proposal.supersedes_id,
            )
            self.facts.append(fact)
            seen.add(key)
            previous.add(fact.id)
            if self.on_fact:
                self.on_fact(fact)

    def _likely_turner(self, run: _SceneRun) -> str:
        """Name who has dug in hardest when the director named nobody: most resisting tactics."""
        tactics = self._recent_tactics(run)
        scores = {
            actor: sum(1 for item in tactics.get(actor, []) if item in RESISTING_TACTICS)
            for actor in run.on_stage
        }
        best = max(scores.values(), default=0)
        if best == 0:
            return policy.next_actor(on_stage=run.on_stage, turns=run.turns)
        return next(actor for actor in run.on_stage if scores[actor] == best)

    def _recent_tactics(self, run: _SceneRun) -> dict[str, list[str]]:
        """List each actor's last few tactics in this scene, oldest first."""
        tactics: dict[str, list[str]] = {}
        for turn in run.turns:
            if turn.kind == "actor" and turn.tactic:
                tactics.setdefault(turn.actor_id, []).append(turn.tactic)
        return {actor: items[-TACTIC_WINDOW:] for actor, items in tactics.items()}

    def _director_context(self, run: _SceneRun, beat: BeatBrief) -> str:
        """Build what the director reads, with the deadlock and repetition signals attached."""
        return director_beat_context(
            scene=run.brief,
            beat=beat,
            turns=run.turns,
            names=self.names,
            gates=run.brief.gate_facts,
            tactics=self._recent_tactics(run),
            used_events=self.used_events,
            clauses=self._clauses.get(run.brief.scene_id + ":" + beat.event_id),
            props=(
                self.inventory.director_view(run.on_stage, run.brief.location_id or "", self.names)
                if self.inventory
                else None
            ),
        )

    def _log(
        self,
        run: _SceneRun,
        index: int,
        beat: BeatBrief,
        mode: str,
        draft: dict | None,
        verdict: _Verdict | None,
        *,
        failed: bool = False,
    ) -> None:
        """Record one director call for director.jsonl, the audit the first runs lacked."""
        if not self.on_direction:
            return
        self.on_direction(
            DirectorEntry(
                decision_id=f"{run.brief.scene_id}:director:{mode}:{len(run.turns)}",
                scene_id=run.brief.scene_id,
                beat_event_id=beat.event_id,
                beat_index=index,
                mode=mode,  # type: ignore[arg-type]
                after_turn=len(run.turns),
                draft=draft,
                achieved=verdict.achieved if verdict else None,
                evidence=verdict.evidence if verdict else [],
                proofs=verdict.proofs if verdict else [],
                missing=verdict.missing if verdict else [],
                turning_actor_id=verdict.turning_actor_id if verdict else "",
                turning_fallback=verdict.turning_fallback if verdict else False,
                stage_event=verdict.stage_event if verdict else "",
                failed=failed,
            )
        )

    # -- memory --------------------------------------------------------------------------

    def _record_turn(self, turn: StageTurn, scene_number: int) -> None:
        """Write one turn into the memory of everyone who perceived it, and into nobody else's."""
        if turn.kind == "world":
            visible = f"({turn.action})" if turn.action else ""
        else:
            speaker = self.names.get(turn.actor_id, turn.actor_id)
            visible = " ".join(
                piece
                for piece in (
                    f"({stage_direction(speaker, turn.action, self.names)})" if turn.action else "",
                    f"{speaker}: {turn.speech}" if turn.speech else "",
                )
                if piece
            )
        # An object move is remembered by exactly those who perceived it, which is not always
        # the turn's own witness list: a hidden object is nobody's business but its holder's,
        # and a hand-over reaches the hands even when the words did not.
        moved = ""
        item_witnesses: list[str] = []
        if turn.item_action is not None:
            item_witnesses = list(turn.item_action.witnesses)
            speaker = self.names.get(turn.actor_id, turn.actor_id)
            line = item_line(turn.item_action, self.names, concealed_from=True)
            moved = f"{speaker} {line}" if line else ""
        for character_id in dict.fromkeys([*turn.witnesses, *item_witnesses]):
            memory = self.memories.get(character_id)
            if memory is None:
                continue
            perceived = character_id in set(turn.witnesses)
            pieces = [
                visible if perceived else "",
                moved if character_id in set(item_witnesses) else "",
            ]
            text = " ".join(piece for piece in pieces if piece)
            if not text:
                continue
            memory.remember(
                kind=self._memory_kind(turn, character_id),
                text=text,
                scene_number=scene_number,
                turn_id=turn.id,
                participants=list(turn.witnesses),
                importance=0.6 if turn.visibility == "whisper" or turn.kind == "world" else 0.5,
            )
        if turn.thought and turn.kind == "actor":
            self.memories[turn.actor_id].remember(
                kind="thought",
                text=f"(pense) {turn.thought}",
                scene_number=scene_number,
                turn_id=turn.id,
                participants=list(turn.witnesses),
                importance=0.55,
            )

    @staticmethod
    def _memory_kind(turn: StageTurn, character_id: str) -> str:
        """Classify one perceived turn for a character's memory stream."""
        if turn.kind == "world":
            return "stage_event"
        return "own_turn" if character_id == turn.actor_id else "observed"

    def _reflect_all(self, scene: SceneBrief, turns: list[StageTurn], on_stage: list[str]) -> None:
        """Close the scene inside every actor who was in it, consolidating their state."""
        for character_id in on_stage:
            witnessed = [turn for turn in turns if character_id in set(turn.witnesses)]
            if not witnessed:
                continue
            log = scene_log(witnessed, self.names, thoughts=False)
            decision_id = f"{scene.scene_id}:reflection:{character_id}"
            if self.on_decision:
                self.on_decision(decision_id)
            if self.on_reflection:
                self.on_reflection(
                    {
                        "decision_id": decision_id,
                        "status": "requested",
                        "context": log,
                        "system_instruction": self.system_prompts[character_id],
                    }
                )
            try:
                reflection = self.reflect(self.system_prompts[character_id], log)
            except NON_DEGRADABLE_ERRORS as exc:
                if self.on_reflection:
                    self.on_reflection(
                        {
                            "decision_id": decision_id,
                            "status": "failed",
                            "error": type(exc).__name__,
                        }
                    )
                raise
            except Exception as exc:
                if self.on_reflection:
                    self.on_reflection(
                        {
                            "decision_id": decision_id,
                            "status": "failed",
                            "error": type(exc).__name__,
                        }
                    )
                self.warnings.append(
                    f"[REFLECTION_FALLBACK] {scene.scene_id}: "
                    f"{self.names.get(character_id, character_id)} no pudo reflexionar."
                )
                continue
            memory = self.memories[character_id]
            memory.remember(
                kind="reflection",
                text=reflection.summary,
                scene_number=scene.number,
                participants=on_stage,
                importance=reflection.importance,
            )
            for belief in reflection.beliefs:
                memory.remember(
                    kind="reflection",
                    text=belief,
                    scene_number=scene.number,
                    participants=on_stage,
                    importance=min(1.0, reflection.importance + 0.1),
                )
            self.states[character_id] = self._consolidate(character_id, scene.number, reflection)
            if self.on_reflection:
                self.on_reflection(
                    {
                        "scene_id": scene.scene_id,
                        "character_id": character_id,
                        "draft": reflection.model_dump(mode="json"),
                        "state": self.states[character_id].model_dump(mode="json"),
                        "decision_id": decision_id,
                        "status": "accepted",
                    }
                )
            if reflection.emotion:
                self.emotions.setdefault(character_id, []).append(reflection.emotion)

    def _consolidate(
        self, character_id: str, scene_number: int, reflection: ReflectionDraft
    ) -> CharacterState:
        """Replace this character's standing towards everyone it just dealt with.

        Replacing rather than appending is the whole point: a character that accumulated every
        past stance would hold "trusts him" and "knows he lied" at once and play neither.
        """
        previous = self.states.get(character_id)
        stances = {item.character_id: item for item in (previous.relationships if previous else [])}
        for item in reflection.relationships:
            if item.character_id != character_id:
                stances[item.character_id] = item
        return CharacterState(
            character_id=character_id,
            scene_number=scene_number,
            emotion=reflection.emotion or (previous.emotion if previous else ""),
            goal=reflection.goal or (previous.goal if previous else ""),
            commitment=reflection.commitment or (previous.commitment if previous else ""),
            cover_story=reflection.cover_story or (previous.cover_story if previous else ""),
            change_condition=reflection.change_condition
            or (previous.change_condition if previous else ""),
            source_turn_id=previous.source_turn_id if previous else "",
            relationships=[stances[key] for key in sorted(stances)],
        )

    def _seed_initial_knowledge(self) -> None:
        """Write each character's starting knowledge into their stream, before scene one."""
        for character_id, dossier in self.dossiers.items():
            memory = self.memories.get(character_id)
            if memory is None:
                continue
            for fact in dossier.initial_knowledge:
                memory.remember(kind="initial", text=fact, scene_number=0, importance=0.5)
            for fact in self.gate_facts.get(character_id, []):
                memory.remember(kind="initial", text=fact, scene_number=0, importance=0.7)

    # -- helpers -------------------------------------------------------------------------

    def _query(self, scene: SceneBrief, objective: str, witnessed: list[StageTurn]) -> str:
        """Build what a character is trying to remember: the scene, its want, and the last words."""
        recent = " ".join(turn.speech for turn in witnessed[-2:] if turn.speech)
        return f"{scene.setting} {objective} {recent}".strip()

    @staticmethod
    def _note_for(notes: list[str], actor_id: str) -> str:
        """Return the note addressed to one actor, if any note is."""
        for note in notes:
            head, _, body = note.partition(":")
            if head.strip().casefold() == actor_id.casefold() and body.strip():
                return body.strip()
        return ""

    def _reject(
        self,
        scene: SceneBrief,
        actor_id: str,
        attempt: int,
        code: str,
        issue: str,
        turn: dict | None,
    ) -> None:
        """Record one rejected turn for the audit."""
        if self.on_rejection:
            self.on_rejection(
                TurnRejection(
                    scene_id=scene.scene_id,
                    actor_id=actor_id,
                    attempt=attempt,
                    code=code,  # type: ignore[arg-type]
                    issue=issue[:400],
                    turn=turn,
                )
            )

    def _note_failure(self, actor_id: str) -> None:
        """Count consecutive provider failures and abort when they stop looking like prompts."""
        self._failures += 1
        if self._failures >= CONSECUTIVE_FAILURE_LIMIT:
            error = StagePerformanceError(
                "Los actores fallaron repetidamente; se detuvo la funcion.",
                details={"consecutive_failures": self._failures, "actor_id": actor_id},
                recommendations=["Revisa el proveedor y vuelve a lanzar la generacion."],
            )
            error.stage = "performance"
            raise error

    def _emit(self, kind: str, message: str) -> None:
        """Report one performance milestone when a callback is configured."""
        if self.on_event:
            self.on_event(kind, message)
