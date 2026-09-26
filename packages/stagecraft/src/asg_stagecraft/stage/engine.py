"""The scene engine: runs one scene of the performance, turn by turn.

The engine owns no model calls of its own. Every one it needs - take a turn, open a beat, check
a beat, reflect - arrives as a callable, so a scene can be played end to end in a test with
canned responses and no provider at all. What the engine owns is the part that must be the same
on every run: the order of turns, who perceived what, what each memory holds, and when a beat is
declared reached or forced.

The loop, in full:

    open the beat  ->  the named actor moves
    a turn arrives ->  validate it, repair once, or skip it
    it is accepted ->  work out who witnessed it, write it into exactly those memories
    every third turn, or at the budget, ask the director whether the beat has landed
    the beat lands ->  open the next one; the budget runs out -> the world intervenes, visibly
    the scene ends ->  every actor reflects, and their state is replaced rather than appended
"""

from __future__ import annotations

from collections.abc import Callable

from ..formats import ActorMemory
from ..runtime.errors import NON_DEGRADABLE_ERRORS, StagePerformanceError
from . import policy
from .memory import CharacterMemory
from .perception import witnesses
from .render import actor_turn_context, director_beat_context, scene_log, transcript
from .schemas import (
    ActorDossier,
    ActorTurnDraft,
    BeatCheckDraft,
    BeatDirection,
    BeatRecord,
    CharacterState,
    ReflectionDraft,
    SceneBrief,
    ScenePerformance,
    StageTurn,
    TurnRejection,
)
from .validation import normalize_turn, validate_turn

# One repair attempt per turn. A second one costs as much as a turn and rarely lands: the actor
# that produced an empty or repeated turn twice is better skipped than argued with.
TURN_ATTEMPTS = 2
# How many consecutive actor failures mean the provider, not the prompt, is the problem.
CONSECUTIVE_FAILURE_LIMIT = 4


class PerformanceEngine:
    """Run scenes of the performance against injected model calls."""

    def __init__(
        self,
        *,
        take_turn: Callable[[str, str, str], ActorTurnDraft],
        open_beat: Callable[[str], BeatDirection],
        check_beat: Callable[[str, bool], BeatCheckDraft],
        reflect: Callable[[str, str], ReflectionDraft],
        dossiers: dict[str, ActorDossier],
        system_prompts: dict[str, str],
        names: dict[str, str],
        gate_facts: dict[str, list[str]],
        whole_cast: list[str],
        language: str,
        actor_memory: ActorMemory = ActorMemory.OWN,
        turns_per_beat: int = 8,
        on_event: Callable[[str, str], None] | None = None,
        on_rejection: Callable[[TurnRejection], None] | None = None,
        on_turn: Callable[[StageTurn, str], None] | None = None,
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
        self.turns_per_beat = turns_per_beat
        self.on_event = on_event
        self.on_rejection = on_rejection
        self.on_turn = on_turn
        self.memories: dict[str, CharacterMemory] = {
            character_id: CharacterMemory(character_id) for character_id in whole_cast
        }
        self.states: dict[str, CharacterState] = {}
        self.warnings: list[str] = []
        self._seed_initial_knowledge()

    def perform_scene(self, scene: SceneBrief) -> ScenePerformance:
        """Play one scene to the end of its last beat and return what was performed."""
        on_stage = [member.character_id for member in scene.cast]
        objectives = {member.character_id: member.objective for member in scene.cast}
        turns: list[StageTurn] = []
        beats: list[BeatRecord] = []
        rejected = skipped = 0

        for index, beat in enumerate(scene.beats):
            record = BeatRecord(event_id=beat.event_id, index=index)
            direction = self._open(scene, beat, turns)
            record.opening_actor_id = direction.opening_actor_id
            record.notes = list(direction.notes)
            requested = direction.opening_actor_id
            notes = list(direction.notes)
            turns_in_beat = 0

            while True:
                actor_id = policy.next_actor(on_stage=on_stage, turns=turns, requested=requested)
                requested = ""
                turn, failures = self._play_turn(
                    scene=scene,
                    beat_index=index,
                    beat=beat,
                    actor_id=actor_id,
                    objective=objectives.get(actor_id, ""),
                    note=self._note_for(notes, actor_id),
                    on_stage=on_stage,
                    turns=turns,
                    number=len(turns) + 1,
                )
                rejected += failures
                if turn is None:
                    skipped += 1
                    self.warnings.append(
                        f"[STAGE_TURN_SKIPPED] {scene.scene_id}: "
                        f"{self.names.get(actor_id, actor_id)} no produjo un turno valido."
                    )
                else:
                    turns.append(turn)
                    self._record_turn(turn, scene.number)
                turns_in_beat += 1
                record.turns += 1

                forced = policy.must_force(turns_in_beat, turns_per_beat=self.turns_per_beat)
                if not forced and not policy.should_check(turns_in_beat):
                    continue

                check = self._check(scene, beat, turns, stalled=forced)
                record.checks += 1
                if check.stage_event:
                    record.stage_events.append(check.stage_event)
                    event_turn = self._stage_event_turn(
                        scene, index, beat, check.stage_event, on_stage, len(turns) + 1
                    )
                    turns.append(event_turn)
                    self._record_turn(event_turn, scene.number)
                if check.achieved:
                    record.achieved = True
                    record.evidence = list(check.evidence)
                    self._emit("beat_achieved", f"{scene.scene_id} alcanzo {beat.event_id}")
                    break
                if forced:
                    record.forced = True
                    self.warnings.append(
                        f"[BEAT_FORCED] {scene.scene_id}: el beat {beat.event_id} no se alcanzo "
                        f"en {turns_in_beat} turnos."
                    )
                    self._emit("beat_forced", f"{scene.scene_id} forzo {beat.event_id}")
                    break
                requested = check.next_actor_id
                notes = list(check.notes)

            beats.append(record)

        if not turns:
            error = StagePerformanceError(
                "Una escena no produjo ni un solo turno valido.",
                details={"scene_id": scene.scene_id, "chapter_id": scene.chapter_id},
                recommendations=[f"Revisa los turnos rechazados en stage/{scene.scene_id}/."],
            )
            error.stage = "performance"
            raise error

        self._reflect_all(scene, turns, on_stage)
        return ScenePerformance(
            scene_id=scene.scene_id,
            number=scene.number,
            chapter_id=scene.chapter_id,
            turns=turns,
            beats=beats,
            rejected=rejected,
            skipped=skipped,
        )

    # -- turns ---------------------------------------------------------------------------

    def _play_turn(
        self,
        *,
        scene: SceneBrief,
        beat_index: int,
        beat,
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
        )
        previous_speech = [
            turn.speech for turn in turns if turn.actor_id == actor_id and turn.speech
        ]
        feedback = ""
        rejections = 0
        for attempt in range(1, TURN_ATTEMPTS + 1):
            try:
                draft = self.take_turn(self.system_prompts[actor_id], context, feedback)
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                rejections += 1
                self._reject(
                    scene, actor_id, attempt, "ACTOR_CALL_FAILED", type(exc).__name__, None
                )
                self._note_failure(actor_id)
                feedback = (
                    "\n\nCORRECCION: el intento anterior no pudo completarse. Vuelve a hacer tu "
                    "movimiento, mas corto y directo."
                )
                continue
            self._clear_failures()
            candidate = normalize_turn(
                draft, on_stage=on_stage, actor_name=self.names.get(actor_id, "")
            )
            try:
                validate_turn(candidate, previous_speech=previous_speech, beat_count=1)
            except ValueError as error:
                rejections += 1
                issue = str(error)
                self._reject(
                    scene,
                    actor_id,
                    attempt,
                    self._code(issue),
                    issue,
                    candidate.model_dump(mode="json"),
                )
                feedback = f"\n\nCORRECCION:\n{issue}\nVuelve a hacer tu movimiento."
                continue
            turn = StageTurn(
                **candidate.model_dump(),
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
            if self.on_turn:
                self.on_turn(turn, context)
            return turn, rejections
        return None, rejections

    def _stage_event_turn(
        self,
        scene: SceneBrief,
        beat_index: int,
        beat,
        text: str,
        on_stage: list[str],
        number: int,
    ) -> StageTurn:
        """Turn the director's intervention into something that happened on stage, for everyone.

        It enters the log as a turn so the narrator reads it exactly like anything else the
        scene produced - the log stays the single source of the story - but it is marked as the
        world's doing, because attributing a thunderclap to whoever happened to be on stage
        first would put words in a character's body.
        """
        return StageTurn(
            action=text,
            visibility="public",
            kind="world",
            id=f"{scene.scene_id}-t{number:03d}",
            scene_id=scene.scene_id,
            number=number,
            actor_id=on_stage[0],
            beat_index=beat_index,
            beat_event_id=beat.event_id,
            witnesses=list(on_stage),
            direction_note="stage_event",
        )

    # -- the director --------------------------------------------------------------------

    def _open(self, scene: SceneBrief, beat, turns: list[StageTurn]) -> BeatDirection:
        """Ask the director to open one beat, falling back to a silent opening."""
        context = director_beat_context(
            scene=scene, beat=beat, turns=turns, names=self.names, gates=scene.gate_facts
        )
        try:
            direction = self.open_beat(context)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception:
            self.warnings.append(
                f"[DIRECTION_FALLBACK] {scene.scene_id}: el beat {beat.event_id} se abrio sin nota."
            )
            return BeatDirection(opening_actor_id=scene.cast[0].character_id, notes=[])
        return direction

    def _check(
        self, scene: SceneBrief, beat, turns: list[StageTurn], *, stalled: bool
    ) -> BeatCheckDraft:
        """Ask the director whether a beat has landed, treating a failure as 'not yet'."""
        context = director_beat_context(
            scene=scene, beat=beat, turns=turns, names=self.names, gates=scene.gate_facts
        )
        try:
            return self.check_beat(context, stalled)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception:
            self.warnings.append(
                f"[BEAT_CHECK_FALLBACK] {scene.scene_id}: no se pudo comprobar {beat.event_id}."
            )
            return BeatCheckDraft(achieved=False, missing="", next_actor_id="")

    # -- memory --------------------------------------------------------------------------

    def _record_turn(self, turn: StageTurn, scene_number: int) -> None:
        """Write one turn into the memory of everyone who perceived it, and into nobody else's."""
        speaker = self.names.get(turn.actor_id, turn.actor_id)
        visible = " ".join(
            piece
            for piece in (
                f"({speaker} {turn.action})" if turn.action else "",
                f"{speaker}: {turn.speech}" if turn.speech else "",
            )
            if piece
        )
        for character_id in turn.witnesses:
            memory = self.memories.get(character_id)
            if memory is None or not visible:
                continue
            memory.remember(
                kind="own_turn" if character_id == turn.actor_id else "observed",
                text=visible,
                scene_number=scene_number,
                turn_id=turn.id,
                participants=list(turn.witnesses),
                importance=0.6 if turn.visibility == "whisper" else 0.5,
            )
        if turn.thought:
            self.memories[turn.actor_id].remember(
                kind="thought",
                text=f"(pense) {turn.thought}",
                scene_number=scene_number,
                turn_id=turn.id,
                participants=list(turn.witnesses),
                importance=0.55,
            )

    def _reflect_all(self, scene: SceneBrief, turns: list[StageTurn], on_stage: list[str]) -> None:
        """Close the scene inside every actor who was in it, consolidating their state."""
        for character_id in on_stage:
            witnessed = [turn for turn in turns if character_id in set(turn.witnesses)]
            if not witnessed:
                continue
            log = scene_log(witnessed, self.names, thoughts=False)
            try:
                reflection = self.reflect(self.system_prompts[character_id], log)
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception:
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

    @staticmethod
    def _code(issue: str) -> str:
        """Classify one validation message into the rejection code it belongs to."""
        if "empty" in issue:
            return "EMPTY_TURN"
        if "internal identifiers" in issue or "heading" in issue:
            return "INTERNAL_IDENTIFIERS"
        if "more than one beat" in issue:
            return "MULTIPLE_BEATS"
        return "REPEATED_LINE"

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
        self._failures = getattr(self, "_failures", 0) + 1
        if self._failures >= CONSECUTIVE_FAILURE_LIMIT:
            error = StagePerformanceError(
                "Los actores fallaron repetidamente; se detuvo la funcion.",
                details={"consecutive_failures": self._failures, "actor_id": actor_id},
                recommendations=["Revisa el proveedor y vuelve a lanzar la generacion."],
            )
            error.stage = "performance"
            raise error

    def _clear_failures(self) -> None:
        """Reset the consecutive-failure counter after a call that worked."""
        self._failures = 0

    def _emit(self, kind: str, message: str) -> None:
        """Report one performance milestone when a callback is configured."""
        if self.on_event:
            self.on_event(kind, message)

    def full_transcript(self, turns: list[StageTurn]) -> str:
        """Render a performed scene for a human reader of the run."""
        return transcript(turns, self.names)
