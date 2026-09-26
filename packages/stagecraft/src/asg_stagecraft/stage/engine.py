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

from ..formats import ActorMemory
from ..runtime.errors import NON_DEGRADABLE_ERRORS, StagePerformanceError
from . import policy
from .memory import CharacterMemory
from .perception import witnesses
from .render import actor_turn_context, director_beat_context, scene_log, transcript
from .schemas import (
    ActorDossier,
    ActorTurnDraft,
    BeatBrief,
    BeatCheckDraft,
    BeatDirection,
    BeatRecord,
    CharacterState,
    DirectorEntry,
    ReflectionDraft,
    SceneBrief,
    ScenePerformance,
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
        turns_per_beat: int = 8,
        reaction_turns: int = REACTION_TURNS,
        coda_turns: int = CODA_TURNS,
        on_event: Callable[[str, str], None] | None = None,
        on_rejection: Callable[[TurnRejection], None] | None = None,
        on_turn: Callable[[StageTurn, str], None] | None = None,
        on_direction: Callable[[DirectorEntry], None] | None = None,
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
        self.reaction_turns = reaction_turns
        self.coda_turns = coda_turns
        self.on_event = on_event
        self.on_rejection = on_rejection
        self.on_turn = on_turn
        self.on_direction = on_direction
        self.memories: dict[str, CharacterMemory] = {
            character_id: CharacterMemory(character_id) for character_id in whole_cast
        }
        self.states: dict[str, CharacterState] = {}
        self.warnings: list[str] = []
        # World events already used anywhere in the play, so the director never reaches for the
        # same device twice: the first real run used three thunderclaps and a power cut.
        self.used_events: list[str] = []
        self._failures = 0
        self._seed_initial_knowledge()

    def perform_scene(self, scene: SceneBrief) -> ScenePerformance:
        """Play one scene to the end of its last beat and return what was performed."""
        run = _SceneRun(
            brief=scene,
            on_stage=[member.character_id for member in scene.cast],
            objectives={member.character_id: member.objective for member in scene.cast},
        )
        beats = [self._perform_beat(run, index, beat) for index, beat in enumerate(scene.beats)]
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
            self._advance(run, index, beat, requested, notes)
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
        first = verdict.turning_actor_id if verdict.turning_actor_id in run.on_stage else ""
        for position in range(self.reaction_turns):
            self._advance(run, index, beat, first if position == 0 else "", verdict.notes)
            record.reaction_turns += 1
            record.turns += 1
        final = self._check(run, index, beat, "final")
        record.checks += 1
        if final.achieved:
            record.intervened = True
            self._land(record, final, run)
            return
        record.forced = True
        self.warnings.append(
            f"[BEAT_FORCED] {run.brief.scene_id}: el beat {beat.event_id} no se alcanzo "
            f"ni con la intervencion del mundo."
        )
        self._emit("beat_forced", f"{run.brief.scene_id} forzo {beat.event_id}")

    def _land(self, record: BeatRecord, verdict: _Verdict, run: _SceneRun) -> None:
        """Close one beat as reached, keeping the turns that prove it."""
        record.achieved = True
        record.evidence = list(verdict.evidence)
        self._emit("beat_achieved", f"{run.brief.scene_id} alcanzo {record.event_id}")

    def _play_coda(self, run: _SceneRun) -> int:
        """Give the play's ending a scene: the most involved characters answer the outcome."""
        if not run.turns or self.coda_turns <= 0:
            return 0
        index = len(run.brief.beats) - 1
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
        notes = [f"{actor}: {CODA_NOTE}" for actor in chosen]
        played = 0
        for actor in chosen:
            self._advance(run, index, beat, actor, notes)
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
    ) -> None:
        """Play the next turn of the scene, recording it or counting it as skipped."""
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
            return
        run.turns.append(turn)
        self._record_turn(turn, run.brief.number)

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
        )
        own = [turn for turn in turns if turn.actor_id == actor_id and turn.kind == "actor"]
        previous_speech = [turn.speech for turn in own if turn.speech]
        previous_actions = [turn.action for turn in own if turn.action]
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
            self._failures = 0
            candidate = normalize_turn(
                draft, on_stage=on_stage, actor_name=self.names.get(actor_id, "")
            )
            try:
                validate_turn(
                    candidate, previous_speech=previous_speech, previous_actions=previous_actions
                )
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
        verdict = self._derive(draft, run, mode)
        self._log(run, index, beat, mode, draft.model_dump(mode="json"), verdict)
        return verdict

    def _derive(self, draft: BeatCheckDraft, run: _SceneRun, mode: str) -> _Verdict:
        """Turn the director's clauses into a verdict the model never gets to declare.

        A clause counts as shown only when it cites a turn that exists. Every missing clause
        keeps the beat open. When the rung requires someone to be named and the director named
        nobody, or gave them no note, the engine fills the gap deterministically and says so.
        """
        known = {turn.id for turn in run.turns}
        evidence: list[str] = []
        missing: list[str] = []
        for part in draft.parts:
            cited = [item for item in part.evidence if item in known]
            if part.shown and cited:
                evidence.extend(item for item in cited if item not in evidence)
            else:
                missing.append(part.part)
        achieved = bool(draft.parts) and not missing
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
            missing=missing,
            turning_actor_id=turning if not achieved else "",
            turning_fallback=fallback,
            next_actor_id=next_actor,
            notes=notes,
            # A beat that lands on the stall reading needs no intervention, so the event the
            # director proposed never happens and must not be logged as if it had.
            stage_event=draft.stage_event.strip() if mode == "stall" and not achieved else "",
        )

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
                scene_id=run.brief.scene_id,
                beat_event_id=beat.event_id,
                beat_index=index,
                mode=mode,  # type: ignore[arg-type]
                after_turn=len(run.turns),
                draft=draft,
                achieved=verdict.achieved if verdict else None,
                evidence=verdict.evidence if verdict else [],
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
                kind=self._memory_kind(turn, character_id),
                text=visible,
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

    def full_transcript(self, turns: list[StageTurn]) -> str:
        """Render a performed scene for a human reader of the run."""
        return transcript(turns, self.names)
