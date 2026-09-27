"""The casting, performance and narration stages, mixed into StoryPipeline.

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

from ..agents import ActorAgent, CastingDirectorAgent, NarratorAgent, StageManagerAgent
from ..planning.promise_brief import chapter_brief
from ..runtime.errors import NON_DEGRADABLE_ERRORS, ASGError
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
from ..writing.acceptance import writer_candidate_issue
from ..writing.assembly import assemble_story
from ..writing.audit import story_metrics, word_count
from . import fallback, voices
from .casting import dossier_index, fallback_bible, gates_for, materialize_bible
from .engine import CODA_TURNS, REACTION_TURNS, PerformanceEngine
from .memory import RECENCY_DECAY, RETRIEVED_RECORDS
from .metrics import simulation_metrics
from .policy import CHECK_EVERY
from .render import actor_system_prompt, scene_log, transcript
from .schemas import (
    BeatBrief,
    CastBible,
    ChapterNarration,
    NarrationArtifact,
    PerformanceArtifact,
    PerformanceSettings,
    SceneBrief,
    SceneCastBrief,
    ScenePerformance,
)
from .validation import REPETITION_THRESHOLD

# "Acto I:", "Act 2 -", "ACTO III." at the head of a title: a script's label, not a chapter's.
_ACT_LABEL = re.compile("^\\s*(?:acto|act)\\s+(?:[ivxlc]+|\\d+)\\s*[:.\\-–—]\\s*", re.IGNORECASE)

CASTING_ATTEMPTS = 2
NARRATION_ATTEMPTS = 2


class SimulationStagesMixin:
    """Provide casting, performance and narration for a simulated Stagecraft run."""

    def _perform_and_narrate(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        play: PlayScript,
        ledger: PromiseLedger | None,
    ) -> None:
        """Cast the actors, play the script, and write the story from what they played."""
        bible = self._cast_actors(request, world, characters, plan, play)
        performance, engine, briefs = self._perform_play(
            request, characters, plan, play, bible, ledger
        )
        story, narration, fallbacks = self._narrate(
            request, characters, plan, play, performance, ledger
        )
        self._finalize_simulation(
            request, plan, bible, performance, narration, engine, briefs, story, fallbacks
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
        for attempt in range(1, CASTING_ATTEMPTS + 1):

            def draw_bible(feedback_snapshot: str = feedback):
                """Draw one cast bible with feedback bound to this attempt."""
                return agent.run(
                    request, world, characters, plan, cast_ids, staging, feedback_snapshot
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
                    draft, cast_ids=cast_ids, characters=characters, plan=plan
                )
            except ValueError as exc:
                issue = str(exc).strip() or type(exc).__name__
                self.repository.save_data(
                    f"casting/attempt-{attempt:03d}.json",
                    {"attempt": attempt, "issue": issue, "bible": draft.model_dump(mode="json")},
                )
                feedback = (
                    "\n\nCASTING REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT CAST BIBLE. "
                    f"The previous one was rejected: {issue}"
                )
                continue
            self.repository.save_json("cast_bible.json", bible)
            self.repository.complete_stage("casting")
            return bible

        warning = (
            "No se pudo escribir la biblia de reparto; los actores se derivan de characters.json."
        )
        self.repository.add_warning(f"[CASTING_FALLBACK] {warning}")
        self._emit("casting_fallback", warning, stage="casting")
        bible = fallback_bible(cast_ids, characters)
        self.repository.save_json("cast_bible.json", bible)
        self.repository.complete_stage("casting")
        return bible

    # -- the performance -----------------------------------------------------------------

    def _perform_play(
        self,
        request: StoryRequest,
        characters: CharactersArtifact,
        plan: StoryPlan,
        play: PlayScript,
        bible: CastBible,
        ledger: PromiseLedger | None,
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
        engine = PerformanceEngine(
            take_turn=lambda system, context, feedback: self._call_agent(
                "actor", lambda: actor.run(system, context, feedback)
            ),
            open_beat=lambda context: self._call_agent(
                "stage_manager", lambda: director.open_beat(context, request.language)
            ),
            check_beat=lambda context, mode: self._call_agent(
                "stage_manager", lambda: director.check(context, request.language, mode=mode)
            ),
            reflect=lambda system, log: self._call_agent(
                "actor", lambda: actor.reflect(system, log, request.language)
            ),
            dossiers=dossiers,
            system_prompts=prompts,
            names=names,
            gate_facts={item: gates_for(bible, item) for item in whole_cast},
            whole_cast=whole_cast,
            language=request.language,
            actor_memory=self.actor_memory,
            turns_per_beat=self.turns_per_beat,
            reaction_turns=REACTION_TURNS,
            coda_turns=CODA_TURNS,
            on_event=lambda kind, message: self._emit(kind, message, stage="performance"),
        )

        briefs = self._scene_briefs(plan, play, bible, ledger, names)
        scenes: list[ScenePerformance] = []
        for index, brief in enumerate(briefs, 1):
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
            try:
                scene = engine.perform_scene(brief)
            except ASGError as error:
                # A performance is a hundred calls long: say which scene it died in.
                error.details.setdefault("scene_id", brief.scene_id)
                raise
            scenes.append(scene)
            self.repository.save_text(
                f"stage/{brief.scene_id}/transcript.md", transcript(scene.turns, names)
            )
            self._emit("scene_performed", f"escena {index} representada", stage="performance")

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

        performance = PerformanceArtifact(
            language=request.language,
            settings=PerformanceSettings(
                actor_memory=self.actor_memory,
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
        )
        self.repository.save_json("performance.json", performance)
        self.repository.save_text(
            "performance.md",
            "\n\n".join(
                f"## {brief.setting}\n\n{transcript(scene.turns, names)}"
                for brief, scene in zip(briefs, scenes, strict=True)
            ),
        )
        for warning in engine.warnings:
            self.repository.add_warning(warning)
        self.repository.complete_stage("performance")
        return performance, engine, briefs

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

    def _narrate(
        self,
        request: StoryRequest,
        characters: CharactersArtifact,
        plan: StoryPlan,
        play: PlayScript,
        performance: PerformanceArtifact,
        ledger: PromiseLedger | None,
    ) -> tuple[str, NarrationArtifact, int]:
        """Write the story from the performance log, through the configured point of view."""
        assert self.repository is not None
        self._notify(84, "narration", "Escribiendo la historia desde la funcion")
        voice = self.narrative_voice
        narrator = voices.narrator_character(
            voice, performance.scenes, protagonist=_protagonist(characters)
        )
        names = {member.character_id: member.name for member in play.cast}
        titles = self._localized_titles(play)

        by_chapter: dict[str, list[ScenePerformance]] = {}
        for scene in performance.scenes:
            by_chapter.setdefault(scene.chapter_id, []).append(scene)

        agent = NarratorAgent(self.provider)
        bodies: list[str] = []
        records: list[ChapterNarration] = []
        fallbacks = 0
        for index, chapter in enumerate(plan.chapters, 1):
            self._notify(
                84 + (index - 1) * 10 // len(plan.chapters),
                "narration",
                f"Narrando el capitulo {index} de {len(plan.chapters)}",
                index,
                len(plan.chapters),
            )
            scenes = by_chapter.get(chapter.id, [])
            visible = [
                turn
                for scene in scenes
                for turn in voices.visible_turns(voice, scene, narrator=narrator)
            ]
            available = sum(len(scene.turns) for scene in scenes)
            key_ids = {item for scene in scenes for beat in scene.beats for item in beat.evidence}
            log = scene_log(visible, names, thoughts=True, key_ids=key_ids)
            body, attempts, source = self._narrate_chapter(
                agent,
                request,
                chapter,
                titles.get(chapter.id, chapter.title),
                voice,
                log,
                bodies[-1] if bodies else "",
                narrator,
                names,
                self._promise_brief(ledger, chapter.id),
                visible,
                index,
            )
            fallbacks += int(source == "fallback")
            bodies.append(body)
            records.append(
                ChapterNarration(
                    chapter_id=chapter.id,
                    chapter_index=index,
                    scene_ids=[scene.scene_id for scene in scenes],
                    turns_available=available,
                    turns_visible=len(visible),
                    words=word_count(body),
                    attempts=attempts,
                    source=source,
                )
            )

        narration = NarrationArtifact(
            narrative_voice=voice,
            narrator_character_id=narrator,
            chapters=records,
        )
        self.repository.save_json("narration.json", narration)
        story = assemble_story(plan, self._presentation_from(play, plan), bodies)
        self.repository.complete_stage("narration")
        return story, narration, fallbacks

    def _narrate_chapter(
        self,
        agent,
        request,
        chapter,
        title,
        voice,
        log,
        previous,
        narrator,
        names,
        promise_brief,
        visible,
        index,
    ) -> tuple[str, int, str]:
        """Narrate one chapter, or render its log deterministically when the model cannot."""
        assert self.repository is not None
        feedback = ""
        for attempt in range(1, NARRATION_ATTEMPTS + 1):

            def narrate_once(feedback_snapshot: str = feedback):
                """Narrate the bound chapter with this attempt's feedback."""
                return agent.run(
                    request,
                    chapter,
                    title,
                    voice,
                    log,
                    previous,
                    narrator_name=names.get(narrator, ""),
                    promise_brief=promise_brief,
                    retry_feedback=feedback_snapshot,
                )

            try:
                candidate = self._call_agent("narrator", narrate_once).strip()
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                # Left on disk like a failed Writer rewrite, so a fallback chapter says why.
                self.repository.save_data(
                    f"narration/chapter-{index:03d}-attempt-{attempt:03d}-error.json",
                    {"attempt": attempt, "status": "failed", "exception_type": type(exc).__name__},
                )
                feedback = (
                    "\n\nRETRY CORRECTION:\nThe previous attempt could not be completed "
                    f"({type(exc).__name__}). Return the complete chapter."
                )
                continue
            self.repository.save_text(
                f"narration/chapter-{index:03d}-attempt-{attempt:03d}.md", candidate
            )
            diagnostic = writer_candidate_issue(candidate, "", [])
            if diagnostic is None:
                self.repository.save_text(f"narration/chapter-{index:03d}.md", candidate)
                return candidate, attempt, "narrator"
            feedback = (
                "\n\nRETRY CORRECTION:\nThe previous attempt was rejected because "
                f"{diagnostic.message}. {diagnostic.retry_instruction}"
            )
        body = fallback.narrate(visible, names)
        warning = f"[NARRATION_FALLBACK] Capitulo {index}: se narro con el narrador de respaldo."
        self.repository.add_warning(warning)
        self._emit("narration_fallback", warning, stage="narration")
        self.repository.save_text(f"narration/chapter-{index:03d}.md", body)
        return body, NARRATION_ATTEMPTS, "fallback"

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
        self.repository.save_json("story_metrics.json", story_metrics(request, plan, story))
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
        return StoryPresentation(
            title=play.title,
            chapters=[
                ChapterPresentation(
                    chapter_id=chapter.id, title=titles.get(chapter.id, chapter.title)
                )
                for chapter in plan.chapters
            ],
        )


def _protagonist(characters: CharactersArtifact) -> str:
    """Name the character the cast declares as its subject, or nobody when none is declared."""
    for item in characters.characters:
        if item.functional_role == "subject":
            return item.id
    return ""


def _holders(known_by: list[str], names: dict[str, str]) -> str:
    """Name who holds one fact, for the director's eyes only."""
    return ", ".join(names.get(item, item) for item in known_by) or "nadie"


def _gate_line(gate, names: dict[str, str]) -> str:
    """Describe one gate for the director: who holds it and who is meant to bring it out."""
    holders = _holders(gate.known_by, names)
    revealer = names.get(gate.revealed_by, gate.revealed_by) if gate.revealed_by else "el mundo"
    return f"{gate.fact} (lo saben: {holders}; lo saca a la luz {revealer} por {gate.how})"


def _without_act_label(title: str) -> str:
    """Drop a leading act label from a title, keeping it whole when nothing else is left."""
    stripped = _ACT_LABEL.sub("", title).strip()
    return stripped or title
