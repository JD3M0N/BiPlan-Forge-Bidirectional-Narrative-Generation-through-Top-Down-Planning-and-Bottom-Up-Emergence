"""The casting and performance stages, mixed into StoryPipeline.

The narration lives in stage/narration_stage.py (7.20), whose mixin this one inherits.

Kept apart from pipeline.py for the same reason script/stages.py is: this is the hybrid half of
the pipeline and it has its own lifecycle, so the narrative stages stay readable and this one
can be reasoned about - or replaced - on its own.

This module assumes it is mixed into StoryPipeline: every method below calls attributes and
helpers pipeline.py defines (self.repository, self.provider, self._notify, self._emit,
self._call_agent, self._promise_brief, self._publish), the same way pipeline.py's own methods do.
"""

from __future__ import annotations

import json
import re

from ..agents import (
    ActorAgent,
    CastingDirectorAgent,
    PropMasterAgent,
    StageManagerAgent,
)
from ..agents.promise_auditor import PromiseStoryAuditorAgent
from ..brief import authored_cast_block
from ..formats import SimulationMode
from ..planning.promise_brief import chapter_brief
from ..runtime.errors import NON_DEGRADABLE_ERRORS, ASGError
from ..runtime.provider import decision_context
from ..schemas import (
    ChapterPresentation,
    CharactersArtifact,
    PlayScript,
    PromiseLedger,
    StoryPlan,
    StoryPresentation,
    StoryRequest,
    WorldArtifact,
)
from ..script.render import staging_index
from ..writing.audit import story_metrics
from .casting import (
    dossier_index,
    fallback_bible,
    gateless,
    gates_for,
    materialize_bible,
    unkept_secrets,
)
from .engine import CODA_TURNS, REACTION_TURNS, PerformanceEngine
from .inventory import StageInventory
from .memory import RECENCY_DECAY, RETRIEVED_RECORDS
from .metrics import simulation_metrics
from .narration_stage import NarrationStageMixin
from .policy import CHECK_EVERY
from .promise_audit import broken_promise_audit, materialize_promise_audit
from .props import fallback_props, materialize_props
from .render import actor_system_prompt, transcript
from .revision import materialize_revision
from .schemas import (
    BeatBrief,
    CastBible,
    PerformanceArtifact,
    PerformanceSettings,
    PropList,
    SceneBrief,
    SceneCastBrief,
    ScenePerformance,
)
from .validation import REPETITION_THRESHOLD

# "Acto I:", "Act 2 -", "ACTO III." at the head of a title: a script's label, not a chapter's.
_ACT_LABEL = re.compile("^\\s*(?:acto|act)\\s+(?:[ivxlc]+|\\d+)\\s*[:.\\-–—]\\s*", re.IGNORECASE)

CASTING_ATTEMPTS = 2
PROPS_ATTEMPTS = 2


class SimulationStagesMixin(NarrationStageMixin):
    """Provide casting, performance and narration for a simulated Stagecraft run."""

    def _perform_and_narrate(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        play: PlayScript,
        ledger: PromiseLedger | None,
        bible: CastBible | None = None,
    ) -> None:
        """Cast or reuse actors, dress the stage if asked, then narrate the performance."""
        if bible is None:
            bible = self._cast_actors(request, world, characters, plan, play)
        props = self._dress_stage(request, world, characters, plan, play, bible)
        performance, engine, briefs = self._perform_play(
            request, world, characters, plan, play, bible, ledger, props
        )
        story, narration, fallbacks, narrated = self._narrate(
            request, characters, plan, play, performance, ledger, world=world, bible=bible
        )
        self._audit_performed_promises(ledger, performance, story)
        self._finalize_simulation(
            request, narrated, bible, performance, narration, engine, briefs, story, fallbacks
        )

    # -- casting -------------------------------------------------------------------------

    def _cast_actors(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        play: PlayScript,
    ) -> CastBible:
        """Build one playable dossier per cast member, or derive a thin one and carry on."""
        assert self.repository is not None
        self._notify(50, "casting", "Preparando a los actores")
        cast_ids = [member.character_id for member in play.cast]
        staging = staging_index(play)
        agent = CastingDirectorAgent(self.provider)
        feedback = ""
        # A bible good in all but its secrets, kept while one repair asks for their gates.
        candidate: CastBible | None = None
        for attempt in range(1, CASTING_ATTEMPTS + 1):

            def draw_bible(feedback_snapshot: str = feedback):
                """Draw one cast bible with feedback bound to this attempt."""
                return agent.run(
                    request,
                    world,
                    characters,
                    plan,
                    cast_ids,
                    staging,
                    feedback_snapshot,
                    authored_cast=authored_cast_block(self.brief),
                    first_scenes=first_scenes_block(play),
                )

            try:
                draft = self._call_agent("casting_director", draw_bible)
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                self.repository.save_data(
                    f"casting/attempt-{attempt:03d}.json",
                    {"attempt": attempt, "status": "failed", "exception_type": type(exc).__name__},
                )
                feedback = (
                    "\n\nCASTING REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT CAST BIBLE. "
                    "The previous attempt could not be completed."
                )
                continue
            try:
                bible = materialize_bible(
                    draft,
                    cast_ids=cast_ids,
                    characters=characters,
                    plan=plan,
                    drop_invalid_gates=attempt == CASTING_ATTEMPTS,
                    future_events=future_events(play),
                    on_stage=event_casts(play) if self.options.typed_clauses else None,
                )
            except ValueError as exc:
                issue = str(exc).strip() or type(exc).__name__
                self.repository.save_data(
                    f"casting/attempt-{attempt:03d}.json",
                    {"attempt": attempt, "issue": issue, "bible": draft.model_dump(mode="json")},
                )
                feedback = (
                    "\n\nCASTING REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT CAST BIBLE. "
                    f"The previous one was rejected: {issue}. Correct what the error names and "
                    "keep every other field of the rejected candidate as it was.\n"
                    f"REJECTED CANDIDATE:\n{draft.model_dump_json()}"
                )
                continue
            secrets = unkept_secrets(bible, plan)
            if secrets and attempt < CASTING_ATTEMPTS:
                candidate = bible
                self.repository.save_data(
                    f"casting/attempt-{attempt:03d}.json",
                    {"attempt": attempt, "issue": "secrets without gates"},
                )
                feedback = (
                    "\n\nCASTING REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT CAST BIBLE. "
                    "The previous one has no knowledge_gates, yet these characters keep a "
                    "secret: "
                    + "; ".join(f"{item.character_id} ({item.secret})" for item in secrets)
                    + ". A secret is a fact some characters hold and others do not: make each "
                    "one a knowledge gate, known_by whoever already holds it, with revealed_by, "
                    "how and revealed_at_event_id when the plan brings it out on stage. Keep "
                    "every other field of the previous candidate as it was.\n"
                    f"PREVIOUS CANDIDATE:\n{draft.model_dump_json()}"
                )
                continue
            return self._keep_bible(bible, plan)

        if candidate is not None:
            return self._keep_bible(candidate, plan)
        warning = (
            "No se pudo escribir la biblia de reparto; los actores se derivan de characters.json."
        )
        self.repository.add_warning(f"[CASTING_FALLBACK] {warning}")
        self._emit("casting_fallback", warning, stage="casting")
        bible = fallback_bible(cast_ids, characters)
        self.repository.save_json("cast_bible.json", bible)
        self.repository.complete_stage("casting")
        return bible

    def _keep_bible(self, bible: CastBible, plan: StoryPlan) -> CastBible:
        """Report what the casting validation dropped or missed, and save the bible."""
        assert self.repository is not None
        facts = [note for note in bible.observations if note.startswith("fact dropped")]
        if facts:
            warning = f"Se quitaron {len(facts)} hechos iniciales que venían del futuro."
            self.repository.add_warning(f"[CAST_FACT_DROPPED] {warning}")
            self._emit("cast_fact_dropped", warning, stage="casting")
        dropped = [note for note in bible.observations if " dropped: " in note]
        if dropped:
            warning = f"Se descartaron {len(dropped)} compuertas inválidas del reparto."
            self.repository.add_warning(f"[CAST_GATE_DROPPED] {warning}")
            self._emit("cast_gate_dropped", warning, stage="casting")
        if gateless(bible, plan):
            warning = "El reparto no tiene compuertas: nadie descubre nada en escena."
            self.repository.add_warning(f"[CAST_NO_GATES] {warning}")
            self._emit("cast_no_gates", warning, stage="casting")
        self.repository.save_json("cast_bible.json", bible)
        self.repository.complete_stage("casting")
        return bible

    # -- the props -----------------------------------------------------------------------

    def _dress_stage(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        play: PlayScript,
        bible: CastBible,
    ) -> PropList | None:
        """Place the objects the performance may handle, or return None when the option is off.

        Returning None rather than an empty list is the whole discipline of this option: the
        engine then builds no arbiter, asks for no object field and renders no object block, so
        a run without an inventory is the run 7.5 produced, prompt for prompt.
        """
        assert self.repository is not None
        if not self.inventory:
            return None
        self._notify(51, "props", "Preparando la utileria")
        cast_ids = [member.character_id for member in play.cast]
        agent = PropMasterAgent(self.provider)
        feedback = ""
        for attempt in range(1, PROPS_ATTEMPTS + 1):

            def draw_props(feedback_snapshot: str = feedback):
                """Draw one set of props with feedback bound to this attempt."""
                return agent.run(
                    request, world, characters, plan, bible, cast_ids, feedback_snapshot
                )

            try:
                draft = self._call_agent("prop_master", draw_props)
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                self.repository.save_data(
                    f"props/attempt-{attempt:03d}.json",
                    {"attempt": attempt, "status": "failed", "exception_type": type(exc).__name__},
                )
                feedback = (
                    "\n\nPROPS REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT PROP LIST. "
                    "The previous attempt could not be completed."
                )
                continue
            try:
                props = materialize_props(draft, world=world, cast_ids=cast_ids, plan=plan)
            except ValueError as exc:
                issue = str(exc).strip() or type(exc).__name__
                self.repository.save_data(
                    f"props/attempt-{attempt:03d}.json",
                    {"attempt": attempt, "issue": issue, "props": draft.model_dump(mode="json")},
                )
                feedback = (
                    "\n\nPROPS REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT PROP LIST. "
                    f"The previous one was rejected: {issue}. Correct what the error names and "
                    "keep everything else of the rejected candidate as it was.\n"
                    f"REJECTED CANDIDATE:\n{draft.model_dump_json()}"
                )
                continue
            self.repository.save_json("props.json", props)
            self.repository.complete_stage("props")
            return props

        warning = "No se pudo vestir el escenario; la utileria se deriva de world.json."
        self.repository.add_warning(f"[PROPS_FALLBACK] {warning}")
        self._emit("props_fallback", warning, stage="props")
        props = fallback_props(world, plan)
        self.repository.save_json("props.json", props)
        self.repository.complete_stage("props")
        return props

    # -- the performance -----------------------------------------------------------------

    def _perform_play(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        play: PlayScript,
        bible: CastBible,
        ledger: PromiseLedger | None,
        props: PropList | None = None,
    ) -> tuple[PerformanceArtifact, PerformanceEngine, list[SceneBrief]]:
        """Let the actors play every scene of the script, scene by scene."""
        assert self.repository is not None
        names = {item.id: item.name for item in characters.characters}
        dossiers = dossier_index(bible)
        whole_cast = [member.character_id for member in play.cast]
        prompts = {
            character_id: actor_system_prompt(
                dossier,
                name=names.get(character_id, character_id),
                language=request.language,
                names=names,
                inventory=props is not None,
            )
            for character_id, dossier in dossiers.items()
        }
        for character_id, prompt in sorted(prompts.items()):
            self.repository.save_data(
                f"stage/actors/{character_id}.json",
                {
                    "character_id": character_id,
                    "system_instruction": prompt,
                    "dossier": dossiers[character_id].model_dump(mode="json"),
                    "knows": gates_for(bible, character_id),
                },
            )

        actor = ActorAgent(self.provider)
        director = StageManagerAgent(self.provider)
        active_decision = {"id": ""}
        inventory = (
            StageInventory(
                props.props,
                actor_memory=self.actor_memory,
                on_item=lambda entry: self.repository.append_jsonl("stage/inventory.jsonl", entry),
            )
            if props is not None
            else None
        )

        def stage_call(name, function):
            """Tag provider records with the stage decision that requested the call."""
            with decision_context(active_decision["id"]):
                return self._call_agent(name, function)

        engine = PerformanceEngine(
            take_turn=lambda system, context, feedback: stage_call(
                "actor",
                lambda: actor.run(system, context, feedback, items=inventory is not None),
            ),
            open_beat=lambda context: stage_call(
                "stage_manager",
                lambda: director.open_beat(context, request.language, request.genre),
            ),
            check_beat=lambda context, mode: stage_call(
                "stage_manager",
                lambda: director.check(
                    context,
                    request.language,
                    mode=mode,
                    genre=request.genre,
                    typed=self.options.typed_clauses,
                ),
            ),
            reflect=lambda system, log: stage_call(
                "actor", lambda: actor.reflect(system, log, request.language)
            ),
            knowledge_gates=bible.knowledge_gates,
            review_world=lambda context: stage_call(
                "world_review", lambda: director.review_world(context)
            ),
            constraints=json.dumps(
                {
                    "premise": request.premise,
                    "rules": world.rules,
                    "constraints": request.constraints,
                },
                ensure_ascii=False,
            ),
            dossiers=dossiers,
            system_prompts=prompts,
            names=names,
            gate_facts={item: gates_for(bible, item) for item in whole_cast},
            whole_cast=whole_cast,
            language=request.language,
            actor_memory=self.actor_memory,
            simulation_mode=self.options.simulation_mode,
            inventory=inventory,
            turns_per_beat=self.turns_per_beat,
            typed_clauses=self.options.typed_clauses,
            reaction_turns=REACTION_TURNS,
            coda_turns=CODA_TURNS,
            on_event=lambda kind, message: self._emit(kind, message, stage="performance"),
            on_decision=lambda decision_id: active_decision.update(id=decision_id),
            on_fact=lambda fact: self.repository.append_jsonl("stage/facts.jsonl", fact),
        )

        for memory in engine.memories.values():
            memory.on_record = lambda record: self.repository.append_jsonl(
                f"memory/{record.character_id}/records.jsonl", record
            )
            for record in memory.records:
                memory.on_record(record)

        briefs = self._scene_briefs(plan, play, bible, ledger, names)
        scenes: list[ScenePerformance] = []
        played_briefs: list[SceneBrief] = []
        index = 0
        if self.options.simulation_mode is SimulationMode.ADAPTIVE:
            self.repository.save_data(
                "active_plan/initial.json",
                {
                    "scene_ids": [item.scene_id for item in briefs],
                    "event_ids": [beat.event_id for item in briefs for beat in item.beats],
                },
            )
        while index < len(briefs):
            brief = briefs[index]
            index += 1
            self._notify(
                52 + (index - 1) * 30 // len(briefs),
                "performance",
                f"Representando la escena {index} de {len(briefs)}",
                index,
                len(briefs),
            )
            self.repository.save_json(f"stage/{brief.scene_id}/brief.json", brief)
            engine.on_rejection = lambda rejection, scene_id=brief.scene_id: (
                self.repository.append_jsonl(f"stage/{scene_id}/rejected.jsonl", rejection)
            )
            engine.on_direction = lambda entry, scene_id=brief.scene_id: (
                self.repository.append_jsonl(f"stage/{scene_id}/director.jsonl", entry)
            )
            engine.on_turn = self._turn_logger(brief.scene_id)
            engine.on_attempt = lambda entry, scene_id=brief.scene_id: self.repository.append_jsonl(
                f"stage/{scene_id}/attempts.jsonl", entry
            )
            engine.on_reflection = lambda entry, scene_id=brief.scene_id: (
                self.repository.append_jsonl(f"stage/{scene_id}/reflections.jsonl", entry)
            )
            engine.on_director_request = lambda entry, scene_id=brief.scene_id: (
                self.repository.append_jsonl(f"stage/{scene_id}/director_requests.jsonl", entry)
            )
            try:
                scene = engine.perform_scene(brief)
            except ASGError as error:
                # A performance is a hundred calls long: say which scene it died in.
                error.details.setdefault("scene_id", brief.scene_id)
                raise
            scenes.append(scene)
            played_briefs.append(brief)
            self.repository.save_data(
                f"stage/{brief.scene_id}/checkpoint.json",
                {
                    "scene_id": brief.scene_id,
                    "completed_scenes": [item.scene_id for item in scenes],
                    "states": {
                        key: value.model_dump(mode="json") for key, value in engine.states.items()
                    },
                    "memory_lengths": {
                        key: len(value.records) for key, value in engine.memories.items()
                    },
                    "inventory": [item.model_dump(mode="json") for item in inventory.snapshot()]
                    if inventory is not None
                    else [],
                },
            )
            self.repository.save_text(
                f"stage/{brief.scene_id}/transcript.md", transcript(scene.turns, names)
            )
            self._emit("scene_performed", f"escena {index} representada", stage="performance")
            changed = self._maybe_revise_future(
                director, request, world, plan, engine, scenes, briefs[index:], names
            )
            if changed is not None:
                briefs = [*briefs[:index], *changed]
                if not changed:
                    self._finish_open_scene(engine, brief, scenes, names)
                    break

        for character_id in sorted(engine.memories):
            memory = engine.memories[character_id]
            self.repository.save_data(
                f"memory/{character_id}/records.json",
                [record.model_dump(mode="json") for record in memory.records],
            )
            self.repository.save_data(
                f"memory/{character_id}/retrievals.json",
                [item.model_dump(mode="json") for item in memory.retrievals],
            )

        all_beats = [beat for scene in scenes for beat in scene.beats]
        outcome = (
            "interrupted"
            if engine.interruption_reason
            else "resolved"
            if all_beats and all(beat.achieved for beat in all_beats) and index == len(briefs)
            else "open"
        )
        performance = PerformanceArtifact(
            narrative_outcome=outcome,
            interruption_reason=engine.interruption_reason,
            planned_events=len(plan.events),
            facts=engine.facts,
            language=request.language,
            settings=PerformanceSettings(
                actor_memory=self.actor_memory,
                simulation_mode=self.options.simulation_mode,
                inventory=inventory is not None,
                turns_per_beat=self.turns_per_beat,
                check_every=CHECK_EVERY,
                reaction_turns=REACTION_TURNS,
                coda_turns=CODA_TURNS,
                retrieved_records=RETRIEVED_RECORDS,
                recency_decay=RECENCY_DECAY,
                repetition_threshold=REPETITION_THRESHOLD,
            ),
            scenes=scenes,
            states=[engine.states[key] for key in sorted(engine.states)],
            warnings=list(engine.warnings),
            props=list(props.props) if props is not None else [],
            inventory=inventory.snapshot() if inventory is not None else [],
        )
        self.repository.save_json("performance.json", performance)
        self.repository.save_text(
            "performance.md",
            "\n\n".join(
                f"## {brief.setting}\n\n{transcript(scene.turns, names)}"
                for brief, scene in zip(played_briefs, scenes, strict=True)
            ),
        )
        for warning in engine.warnings:
            self.repository.add_warning(warning)
        self.repository.complete_stage("performance")
        return performance, engine, played_briefs

    def _finish_open_scene(self, engine, brief, scenes, names) -> None:
        """Record a short open coda when adaptation removes the original last scene."""
        assert self.repository is not None
        if brief.closes_play:
            return
        scenes[-1] = engine.perform_open_coda(brief, scenes[-1])
        self.repository.save_text(
            f"stage/{brief.scene_id}/transcript.md", transcript(scenes[-1].turns, names)
        )
        self.repository.save_data(
            f"stage/{brief.scene_id}/checkpoint.json",
            {
                "scene_id": brief.scene_id,
                "completed_scenes": [item.scene_id for item in scenes],
                "states": {
                    key: value.model_dump(mode="json") for key, value in engine.states.items()
                },
                "memory_lengths": {
                    key: len(value.records) for key, value in engine.memories.items()
                },
            },
        )

    def _maybe_revise_future(
        self, director, request, world, plan, engine, scenes, remaining, names
    ) -> list[SceneBrief] | None:
        """Return a revised suffix when a played scene changes what can happen next."""
        if self.options.simulation_mode is not SimulationMode.ADAPTIVE or not remaining:
            return None
        missed = any(not beat.achieved for beat in scenes[-1].beats)
        if not missed and not self._future_conflict(
            director, request, world, engine, scenes, remaining, names
        ):
            return None
        return self._revise_future(director, request, world, plan, engine, scenes, remaining, names)

    def _future_conflict(self, director, request, world, engine, scenes, remaining, names) -> bool:
        """Ask whether a witnessed action contradicts an event still to be played."""
        assert self.repository is not None
        current = scenes[-1]
        context = json.dumps(
            {
                "premise": request.premise,
                "constraints": request.constraints,
                "world_rules": world.rules,
                "accepted_facts": [
                    fact.model_dump(mode="json")
                    for fact in engine.facts
                    if fact.status == "established"
                ],
                "performed": [
                    {"scene_id": scene.scene_id, "transcript": transcript(scene.turns, names)}
                    for scene in scenes
                ],
                "future_events": [
                    {"event_id": beat.event_id, "outcome": beat.outcome}
                    for scene in remaining
                    for beat in scene.beats
                ],
            },
            ensure_ascii=False,
        )
        decision_id = f"conflict-{len(scenes):03d}"
        attempts_path = "active_plan/conflict_attempts.jsonl"
        self.repository.append_jsonl(
            attempts_path,
            {"decision_id": decision_id, "status": "requested", "prompt": context},
        )
        try:
            with decision_context(decision_id):
                proposal = self._call_agent(
                    "stage_manager", lambda: director.future_conflict(context)
                )
        except NON_DEGRADABLE_ERRORS as exc:
            self.repository.append_jsonl(
                attempts_path,
                {"decision_id": decision_id, "status": "failed", "error": type(exc).__name__},
            )
            raise
        except Exception as exc:
            self.repository.append_jsonl(
                attempts_path,
                {"decision_id": decision_id, "status": "failed", "error": type(exc).__name__},
            )
            return False
        self.repository.append_jsonl(
            attempts_path,
            {
                "decision_id": decision_id,
                "status": "proposed",
                "draft": proposal.model_dump(mode="json"),
            },
        )
        future = {beat.event_id for scene in remaining for beat in scene.beats}
        known = {fact.source_turn_id for fact in engine.facts}
        valid = (
            set(proposal.invalidated_event_ids) <= future
            and bool(proposal.evidence_turn_ids)
            and set(proposal.evidence_turn_ids) <= known
        )
        self.repository.save_data(
            f"active_plan/conflict-{len(scenes):03d}.json",
            {
                "after_scene": current.scene_id,
                "proposal": proposal.model_dump(mode="json"),
                "accepted": bool(proposal.invalidated_event_ids) and valid,
            },
        )
        return bool(proposal.invalidated_event_ids) and valid

    def _revise_future(
        self, director, request, world, plan, engine, scenes, remaining, names
    ) -> list[SceneBrief]:
        """Revise one unperformed suffix, or stop with an honest open ending."""
        assert self.repository is not None
        achieved = {beat.event_id for scene in scenes for beat in scene.beats if beat.achieved}
        context = json.dumps(
            {
                "premise": request.premise,
                "constraints": request.constraints,
                "world_rules": world.rules,
                "accepted_facts": [
                    fact.model_dump(mode="json")
                    for fact in engine.facts
                    if fact.status == "established"
                ],
                "performed": [
                    {
                        "scene_id": scene.scene_id,
                        "transcript": transcript(scene.turns, names),
                        "beats": [
                            {
                                "event_id": beat.event_id,
                                "achieved": beat.achieved,
                                "missing": beat.missing,
                            }
                            for beat in scene.beats
                        ],
                    }
                    for scene in scenes
                ],
                "remaining": [item.model_dump(mode="json") for item in remaining],
            },
            ensure_ascii=False,
        )
        feedback = ""
        attempts_path = f"active_plan/revision-{len(scenes):03d}-attempts.jsonl"
        for attempt in range(1, 3):
            decision_id = f"revision-{len(scenes):03d}-a{attempt}"
            prompt = context + feedback
            self.repository.append_jsonl(
                attempts_path,
                {"decision_id": decision_id, "status": "requested", "prompt": prompt},
            )
            try:
                with decision_context(decision_id):
                    proposal = self._call_agent(
                        "stage_manager",
                        lambda prompt_snapshot=prompt: director.revise_future(
                            prompt_snapshot, request.language
                        ),
                    )
            except NON_DEGRADABLE_ERRORS as exc:
                self.repository.append_jsonl(
                    attempts_path,
                    {"decision_id": decision_id, "status": "failed", "error": type(exc).__name__},
                )
                raise
            except Exception as exc:
                self.repository.append_jsonl(
                    attempts_path,
                    {"decision_id": decision_id, "status": "failed", "error": type(exc).__name__},
                )
                feedback = (
                    f"\nPrevious revision failed: {type(exc).__name__}. "
                    "Return all remaining scenes."
                )
                continue
            self.repository.append_jsonl(
                attempts_path,
                {
                    "decision_id": decision_id,
                    "status": "proposed",
                    "draft": proposal.model_dump(mode="json"),
                },
            )
            try:
                changed = materialize_revision(proposal, remaining, plan, achieved, engine.facts)
            except ValueError as exc:
                self.repository.append_jsonl(
                    attempts_path,
                    {"decision_id": decision_id, "status": "rejected", "issue": str(exc)},
                )
                feedback = f"\nRevision rejected: {exc}. Return a complete corrected revision."
                continue
            self.repository.append_jsonl(
                attempts_path,
                {"decision_id": decision_id, "status": "accepted"},
            )
            self.repository.save_data(
                f"active_plan/revision-{len(scenes):03d}.json",
                {
                    "after_scene": scenes[-1].scene_id,
                    "attempt": attempt,
                    "reason": proposal.reason,
                    "scenes": [item.model_dump(mode="json") for item in changed],
                    "omitted_scene_ids": [
                        item.scene_id
                        for item in remaining
                        if item.scene_id not in {new.scene_id for new in changed}
                    ],
                },
            )
            return changed
        engine.interruption_reason = "future_revision_failed"
        warning = (
            f"[REVISION_FAILED] {scenes[-1].scene_id}: "
            "no se pudo revisar el futuro; interrupcion tecnica."
        )
        self.repository.add_warning(warning)
        self.repository.save_data(
            f"active_plan/revision-{len(scenes):03d}-failed.json",
            {"after_scene": scenes[-1].scene_id, "status": "failed", "feedback": feedback},
        )
        return []

    def _turn_logger(self, scene_id: str):
        """Build the callback that logs each performed turn of one scene as it happens."""
        assert self.repository is not None
        repository = self.repository

        def log_turn(turn, context: str) -> None:
            """Log one turn, and the prompt block that produced it when there was one."""
            repository.append_jsonl(f"stage/{scene_id}/turns.jsonl", turn)
            # A world event has no prompt behind it; an empty context would claim one.
            if context:
                repository.append_jsonl(
                    f"stage/{scene_id}/contexts.jsonl",
                    {"turn_id": turn.id, "actor_id": turn.actor_id, "context": context},
                )

        return log_turn

    def _scene_briefs(
        self,
        plan: StoryPlan,
        play: PlayScript,
        bible: CastBible,
        ledger: PromiseLedger | None,
        names: dict[str, str],
    ) -> list[SceneBrief]:
        """Turn the validated script into one brief per scene, in performance order."""
        events = {event.id: event for event in plan.events}
        chapters = {chapter.id: chapter for chapter in plan.chapters}
        faces = {item.character_id: item.public_face for item in bible.dossiers}
        briefs: list[SceneBrief] = []
        for act in play.acts:
            chapter = chapters[act.chapter_id]
            for scene in act.scenes:
                beats = [
                    BeatBrief(
                        event_id=event_id,
                        title=events[event_id].title,
                        purpose=events[event_id].purpose,
                        outcome=events[event_id].outcome,
                        conflict=events[event_id].conflict,
                        promise_brief=chapter_brief(ledger, chapter, [events[event_id]]),
                        required_gates=[
                            (
                                f"{gate.id}: {gate.fact} ({gate.how}, "
                                f"{names.get(gate.revealed_by, gate.revealed_by)})"
                            )
                            for gate in bible.knowledge_gates
                            if gate.revealed_at_event_id == event_id
                        ],
                    )
                    for event_id in scene.event_ids
                    if event_id in events
                ]
                if not beats:
                    continue
                briefs.append(
                    SceneBrief(
                        scene_id=scene.id,
                        number=len(briefs) + 1,
                        chapter_id=act.chapter_id,
                        act_number=act.number,
                        location_id=scene.location_id,
                        setting=scene.setting,
                        cast=[
                            SceneCastBrief(
                                character_id=member.character_id,
                                name=names.get(member.character_id, member.character_id),
                                objective=member.objective,
                                public_face=faces.get(member.character_id, ""),
                            )
                            for member in scene.cast
                        ],
                        beats=beats,
                        gate_facts=[_gate_line(gate, names) for gate in bible.knowledge_gates],
                        scripted_lines=[
                            line.text for line in scene.lines if line.kind == "dialogue"
                        ],
                    )
                )
        # The last scene carries the ending, so it is the one that earns a coda: without it the
        # first real runs stopped on whatever line happened to land the final beat.
        if briefs:
            briefs[-1] = briefs[-1].model_copy(update={"closes_play": True})
        return briefs

    # -- narration -----------------------------------------------------------------------

    def _audit_performed_promises(self, ledger, performance, story) -> None:
        """Replace the script audit with an audit of the narrated performance."""
        assert self.repository is not None
        if ledger is None:
            return
        earlier = self.repository.run_dir / "promise_audit.json"
        if earlier.is_file():
            self.repository.save_data(
                "script_promise_audit.json", json.loads(earlier.read_text(encoding="utf-8"))
            )
        turns = [
            {
                "id": turn.id,
                "action": turn.action,
                "speech": turn.speech,
                "kind": turn.kind,
                "visibility": turn.visibility,
            }
            for scene in performance.scenes
            for turn in scene.turns
        ]
        auditor = PromiseStoryAuditorAgent(self.provider)
        represented = "\n".join(f"{turn['id']} {turn['action']} {turn['speech']}" for turn in turns)
        for source, text, filename in (
            ("performance", represented, "performance_promise_audit.json"),
            ("narration", story, "promise_audit.json"),
        ):
            try:
                draft = self._call_agent(
                    "promise_auditor", lambda text=text: auditor.run(ledger, text, turns)
                )
                self.repository.save_json(f"stage/{source}_promise_audit_draft.json", draft)
                result = materialize_promise_audit(draft, ledger, performance, text).model_copy(
                    update={"source": source}
                )
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                result = broken_promise_audit(ledger).model_copy(update={"source": source})
                self.repository.add_warning(
                    f"[PROMISE_AUDIT_FALLBACK] {source}: {type(exc).__name__}"
                )
            self.repository.save_json(filename, result)

    # -- finishing -----------------------------------------------------------------------

    def _finalize_simulation(
        self, request, plan, bible, performance, narration, engine, briefs, story, fallbacks
    ) -> None:
        """Persist the measured performance and publish the narrated story."""
        assert self.repository is not None
        metrics = simulation_metrics(
            profile=request.narrative_profile,
            performance=performance,
            scripted_by_scene={brief.scene_id: brief.scripted_lines for brief in briefs},
            memories=engine.memories,
            names=engine.names,
            story=story,
            narration_fallbacks=fallbacks,
            bible=bible,
            emotions=engine.emotions,
        )
        metrics = metrics.model_copy(update={"narrative_voice": narration.narrative_voice})
        self.repository.save_json("simulation_metrics.json", metrics)
        measured_plan = plan
        if self.options.simulation_mode is SimulationMode.ADAPTIVE:
            performed_ids = {
                beat.event_id
                for scene in performance.scenes
                for beat in scene.beats
                if beat.achieved
            }
            measured_plan = plan.model_copy(
                update={"events": [event for event in plan.events if event.id in performed_ids]}
            )
        self.repository.save_json(
            "story_metrics.json", story_metrics(request, measured_plan, story)
        )
        self._publish(story, "Guardando la historia", "Historia simulada terminada")

    def _localized_titles(self, play: PlayScript) -> dict[str, str]:
        """Read the localized chapter titles the script stage already wrote for this run.

        materialize_act mints an act's title from the frozen plan, which is written in English,
        so the acts themselves cannot supply them. script_presentation.json can, and falling
        back to the act title keeps a run readable if that artifact is ever missing. An act label
        ("Acto I:") belongs to the script; the story is prose, so it is dropped.
        """
        assert self.repository is not None
        path = self.repository.run_dir / "script_presentation.json"
        titles = {act.chapter_id: act.title for act in play.acts}
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return titles
        for chapter in document.get("chapters") or []:
            if isinstance(chapter, dict) and chapter.get("chapter_id") and chapter.get("title"):
                titles[chapter["chapter_id"]] = chapter["title"]
        return {key: _without_act_label(value) for key, value in titles.items()}

    def _presentation_from(self, play: PlayScript, plan: StoryPlan) -> StoryPresentation:
        """Rebuild the localized presentation the assembler needs for the narrated story."""
        titles = self._localized_titles(play)
        if self.options.simulation_mode is SimulationMode.ADAPTIVE:
            titles = {
                chapter.id: f"Cap\u00edtulo {index}"
                for index, chapter in enumerate(plan.chapters, 1)
            }
        return StoryPresentation(
            title=play.title,
            chapters=[
                ChapterPresentation(
                    chapter_id=chapter.id, title=titles.get(chapter.id, chapter.title)
                )
                for chapter in plan.chapters
            ],
        )


def _holders(known_by: list[str], names: dict[str, str]) -> str:
    """Name who holds one fact, for the director's eyes only."""
    return ", ".join(names.get(item, item) for item in known_by) or "nadie"


def _gate_line(gate, names: dict[str, str]) -> str:
    """Describe one gate for the director: who holds it and who is meant to bring it out."""
    holders = _holders(gate.known_by, names)
    revealer = names.get(gate.revealed_by, gate.revealed_by) if gate.revealed_by else "el mundo"
    return f"{gate.fact} (lo saben: {holders}; lo saca a la luz {revealer} por {gate.how})"


def _scenes_in_order(play: PlayScript) -> list:
    """Every scene of the script, act after act."""
    return [scene for act in play.acts for scene in act.scenes]


def event_casts(play: PlayScript) -> dict[str, set[str]]:
    """Map every plan event to everyone on stage in the scenes that play it."""
    casts: dict[str, set[str]] = {}
    for scene in _scenes_in_order(play):
        for event_id in scene.event_ids:
            casts.setdefault(event_id, set()).update(item.character_id for item in scene.cast)
    return casts


def future_events(play: PlayScript) -> dict[str, set[str]]:
    """Map each character to the events played from their first scene on (7.17).

    Those are what their initial knowledge may never come from: an event in their first scene
    has not happened yet when they walk on.
    """
    scenes = _scenes_in_order(play)
    future: dict[str, set[str]] = {}
    for index, scene in enumerate(scenes):
        for member in scene.cast:
            if member.character_id not in future:
                future[member.character_id] = {
                    event_id for later in scenes[index:] for event_id in later.event_ids
                }
    return future


def first_scenes_block(play: PlayScript) -> str:
    """Tell the casting director each character's first scene and the sources they may cite.

    7.19: the 7.18 islands run cited the first event as the source of four starting facts, all
    dropped; naming the earlier events, and only those, says where a fact may come from.
    """
    names = {member.character_id: member.name for member in play.cast}
    future = future_events(play)
    seen: dict[str, tuple[list[str], list[str]]] = {}
    earlier: list[str] = []
    for scene in _scenes_in_order(play):
        for member in scene.cast:
            past = [item for item in earlier if item not in future[member.character_id]]
            seen.setdefault(member.character_id, (list(scene.event_ids), past))
        earlier.extend(item for item in scene.event_ids if item not in earlier)
    return "\n".join(
        f"- {character_id} ({names.get(character_id, character_id)}): first on stage in the "
        f"scene of {', '.join(events) or 'no event'}; knowledge_sources may be: "
        f"{', '.join(['world', 'backstory', *before])}"
        for character_id, (events, before) in seen.items()
    )


def _without_act_label(title: str) -> str:
    """Drop a leading act label from a title, keeping it whole when nothing else is left."""
    stripped = _ACT_LABEL.sub("", title).strip()
    return stripped or title
