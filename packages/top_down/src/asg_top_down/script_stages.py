"""Theater-script pipeline stages, mixed into StoryPipeline.

Kept apart from pipeline.py on purpose: the two script methods are an open experiment (see
TODO.md), and the losing one gets deleted once measured. Isolating its orchestration here means
that deletion touches this one file instead of pipeline.py's narrative stages.

This module assumes it is mixed into StoryPipeline: every method below calls attributes and
helpers pipeline.py defines (self.repository, self.provider, self._notify, self._emit,
self._call_agent, self._promise_brief, self._notes_for_chapter, self._validate_presentation,
self._validate_note_references, self._audit_promises), the same way pipeline.py's own methods
do.
"""

from __future__ import annotations

from .agents import PlaywrightAgent, ScriptAdapterAgent, ScriptCriticAgent, ScriptWriterAgent
from .audit import script_metrics, word_count
from .errors import NON_DEGRADABLE_ERRORS, ScriptValidationError
from .formats import ScriptMethod
from .graph import relevant_prior_events
from .promise_brief import critic_obligations
from .schemas import (
    ActScript,
    ActScriptDraft,
    ChapterPlan,
    ChapterRevisionAttempt,
    ChapterRevisionResult,
    CharacterProfile,
    CharactersArtifact,
    PlayScript,
    PlotEvent,
    PromiseLedger,
    RevisionNote,
    RevisionReport,
    ScriptFrame,
    ScriptPresentation,
    StoryPlan,
    StoryPresentation,
    StoryRequest,
    StoryReview,
    WorldArtifact,
)
from .script import (
    act_anchor_index,
    assemble_play,
    materialize_act,
    normalized_frame,
    revision_issue,
)
from .script_render import render_act, render_script, staging_index

SCRIPT_ACT_ATTEMPTS = 3
SCRIPT_REVISION_ATTEMPTS = 2


class ScriptStagesMixin:
    """Provide the native and adapted theater-script stages for StoryPipeline."""

    def _write_script(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        ledger: PromiseLedger | None,
    ) -> PlayScript:
        """Draft, critique, and revise a native theater script from the frozen plan."""
        presentation, acts = self._draft_acts(request, world, characters, plan, ledger)
        draft_play = assemble_play(
            presentation, characters, acts, language=request.language, method=ScriptMethod.NATIVE
        )
        self.repository.save_text("draft.md", render_script(draft_play))
        review = self._critique_script(
            request, world, characters, plan, presentation, draft_play, ledger
        )
        if review is None:
            return draft_play
        acts = self._revise_acts(
            request, world, characters, plan, presentation, acts, review, ledger
        )
        return assemble_play(
            presentation, characters, acts, language=request.language, method=ScriptMethod.NATIVE
        )

    def _draft_acts(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        ledger: PromiseLedger | None,
    ) -> tuple[ScriptPresentation, list[ActScript]]:
        """Use the Playwright to localize titles and stage the first act of every chapter."""
        assert self.repository is not None
        playwright = PlaywrightAgent(self.provider)

        def create_presentation():
            """Create localized script titles, act titles, and printed-script frame."""
            return playwright.presentation(request, plan, characters)

        presentation = self._call_agent("playwright", create_presentation)
        self._validate_presentation(plan, presentation)
        presentation = presentation.model_copy(
            update={"frame": normalized_frame(presentation.frame, characters)}
        )
        self.repository.save_json("script_presentation.json", presentation)
        event_by_id = {event.id: event for event in plan.events}
        acts: list[ActScript] = []
        for index, chapter in enumerate(plan.chapters, 1):
            self._notify(
                52 + (index - 1) * 24 // len(plan.chapters),
                "drafting",
                f"Escribiendo el acto {index} de {len(plan.chapters)}",
                index,
                len(plan.chapters),
            )
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            history = relevant_prior_events(plan, {event.id for event in events})
            character_ids = {item for event in events for item in event.character_ids}
            relevant = [item for item in characters.characters if item.id in character_ids]
            anchor_index = act_anchor_index(chapter, plan, world, characters)
            previous_act_text = (
                render_act(acts[-1], scene_label=presentation.frame.scene_label) if acts else ""
            )

            def draft_act(
                feedback: str = "",
                character_snapshot=relevant or characters.characters,
                chapter_snapshot=chapter,
                event_snapshot=events,
                history_snapshot=history,
                previous_snapshot=previous_act_text,
                anchor_snapshot=anchor_index,
            ) -> ActScriptDraft:
                """Draft one act candidate with loop values bound to this iteration."""
                return playwright.run(
                    request,
                    world,
                    character_snapshot,
                    plan,
                    presentation,
                    chapter_snapshot,
                    event_snapshot,
                    history_snapshot,
                    previous_snapshot,
                    anchor_snapshot,
                    self._promise_brief(ledger, chapter_snapshot.id),
                    feedback,
                )

            act = self._act_with_repair(
                agent="playwright",
                produce=draft_act,
                chapter=chapter,
                number=index,
                plan=plan,
                world=world,
                characters=characters,
                directory="acts",
                stage="drafting",
            )
            self.repository.save_json(f"acts/act-{index:03d}.json", act)
            acts.append(act)
        self.repository.complete_stage("drafting")
        return presentation, acts

    def _act_with_repair(
        self,
        *,
        agent: str,
        produce,
        chapter: ChapterPlan,
        number: int,
        plan: StoryPlan,
        world: WorldArtifact,
        characters: CharactersArtifact,
        directory: str,
        stage: str,
    ) -> ActScript:
        """Run the bounded repair loop for one act and return the first act that validates."""
        assert self.repository is not None
        anchor_index = act_anchor_index(chapter, plan, world, characters)
        feedback = ""
        validation_errors: list[str] = []
        for attempt in range(1, SCRIPT_ACT_ATTEMPTS + 1):

            def draw_act(feedback_snapshot: str = feedback) -> ActScriptDraft:
                """Draw one act candidate with feedback bound to this attempt."""
                return produce(feedback_snapshot)

            try:
                draft = self._call_agent(agent, draw_act)
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                self.repository.save_data(
                    f"{directory}/act-{number:03d}-attempt-{attempt:03d}.json",
                    {"attempt": attempt, "status": "failed", "exception_type": type(exc).__name__},
                )
                validation_errors.append(type(exc).__name__)
                feedback = (
                    "\n\nACT REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT ACT. The previous "
                    f"attempt could not be completed ({type(exc).__name__}).\n{anchor_index}"
                )
                continue
            try:
                act = materialize_act(
                    draft,
                    chapter=chapter,
                    number=number,
                    plan=plan,
                    world=world,
                    characters=characters,
                )
            except ValueError as exc:
                feedback = self._record_rejected_act(
                    draft, directory, number, attempt, exc, anchor_index
                )
                validation_errors.append(str(exc))
                continue
            return act
        error = ScriptValidationError(
            "No se obtuvo un acto valido tras varios intentos.",
            details={
                "act": number,
                "chapter_id": chapter.id,
                "attempts": SCRIPT_ACT_ATTEMPTS,
                "validation_errors": validation_errors,
            },
            recommendations=[f"Revisa los intentos guardados bajo {directory}/."],
        )
        error.stage = stage
        raise error

    def _record_rejected_act(
        self,
        draft: ActScriptDraft,
        directory: str,
        number: int,
        attempt: int,
        error: ValueError,
        anchor_index: str,
    ) -> str:
        """Persist one rejected act and build the repair block reinjected verbatim."""
        assert self.repository is not None
        issue = str(error).strip() or type(error).__name__
        self.repository.save_data(
            f"{directory}/act-{number:03d}-attempt-{attempt:03d}.json",
            {
                "attempt": attempt,
                "status": "rejected",
                "issue": issue,
                "act": draft.model_dump(mode="json"),
            },
        )
        self._emit(
            "act_rejected", f"acto {number} rechazado: {issue}", stage=self.progress["stage"]
        )
        return (
            "\n\nACT REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT ACT. "
            f"The previous act was rejected: {issue}. The plan stays frozen: repair the "
            f"staging, never the events.\n{anchor_index}"
        )

    def _critique_script(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        presentation: ScriptPresentation,
        play: PlayScript,
        ledger: PromiseLedger | None,
    ) -> StoryReview | None:
        """Critique the complete draft script, or degrade to delivering the drafted acts."""
        assert self.repository is not None
        self._notify(78, "critique", "Analizando el drama del guion completo")
        rendered = render_script(play)
        staging = staging_index(play)
        obligations = critic_obligations(ledger)
        try:

            def critique_script_draft():
                """Critique the bound complete draft script."""
                return ScriptCriticAgent(self.provider).run(
                    request, world, characters, plan, presentation, rendered, staging, obligations
                )

            review = self._call_agent("script_critic", critique_script_draft)
            self.repository.save_json("review.json", review)
            self._validate_note_references(review.notes, plan)
            self._audit_promises(ledger, review)
            self.repository.complete_stage("critique")
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            warning = (
                "La critica del guion no pudo completarse; se entrego el borrador por actos "
                f"({type(exc).__name__})."
            )
            self.repository.add_warning(warning)
            self._emit("quality_fallback", warning, stage=self.progress["stage"])
            return None
        return review

    def _revise_acts(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        presentation: ScriptPresentation,
        acts: list[ActScript],
        review: StoryReview,
        ledger: PromiseLedger | None,
    ) -> list[ActScript]:
        """Run the Script Writer for every act with notes, with one bounded corrective retry."""
        assert self.repository is not None
        writer = ScriptWriterAgent(self.provider)
        event_by_id = {event.id: event for event in plan.events}
        revised_acts: list[ActScript] = []
        revision_results: list[ChapterRevisionResult] = []
        for index, (chapter, act) in enumerate(zip(plan.chapters, acts, strict=True), 1):
            self._notify(
                84 + (index - 1) * 12 // len(plan.chapters),
                "revision",
                f"Corrigiendo acto {index} de {len(plan.chapters)}",
                index,
                len(plan.chapters),
            )
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            notes = self._notes_for_chapter(review.notes, chapter, events)
            if notes:
                character_ids = {item for event in events for item in event.character_ids}
                relevant = [item for item in characters.characters if item.id in character_ids]
                accepted, result = self._revise_one_act(
                    writer,
                    request,
                    world,
                    characters,
                    relevant or characters.characters,
                    plan,
                    presentation,
                    chapter,
                    events,
                    notes,
                    act,
                    revised_acts[-1] if revised_acts else None,
                    index,
                    self._promise_brief(ledger, chapter.id),
                )
            else:
                accepted, result = act, self._unrevised_act_result(chapter, index, act)
            revised_acts.append(accepted)
            revision_results.append(result)
            self.repository.save_json(f"revisions/act-{index:03d}.json", accepted)
            self.repository.save_json(
                "revision_report.json", RevisionReport(chapters=revision_results)
            )
        self.repository.complete_stage("revision")
        return revised_acts

    @staticmethod
    def _unrevised_act_result(
        chapter: ChapterPlan, chapter_index: int, act: ActScript
    ) -> ChapterRevisionResult:
        """Record an act the script critic left untouched, so no Script Writer call is spent."""
        words = sum(word_count(line.text) for scene in act.scenes for line in scene.lines)
        return ChapterRevisionResult(
            chapter_id=chapter.id,
            chapter_index=chapter_index,
            note_ids=[],
            draft_words=words,
            attempts=[],
            final_source="draft",
            final_words=words,
        )

    def _revise_one_act(
        self,
        writer: ScriptWriterAgent,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        relevant_characters: list[CharacterProfile],
        plan: StoryPlan,
        presentation: ScriptPresentation,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        notes: list[RevisionNote],
        original_act: ActScript,
        previous_revised_act: ActScript | None,
        chapter_index: int,
        promise_brief: str = "",
    ) -> tuple[ActScript, ChapterRevisionResult]:
        """Return the first valid Script Writer candidate or the safe original act."""
        assert self.repository is not None
        anchor_index = act_anchor_index(chapter, plan, world, characters)
        draft_words = sum(
            word_count(line.text) for scene in original_act.scenes for line in scene.lines
        )
        previous_text = (
            render_act(previous_revised_act, scene_label=presentation.frame.scene_label)
            if previous_revised_act
            else ""
        )
        attempts: list[ChapterRevisionAttempt] = []
        retry_feedback = ""
        for attempt in range(1, SCRIPT_REVISION_ATTEMPTS + 1):
            prefix = f"writer/act-{chapter_index:03d}-attempt-{attempt:03d}"
            try:

                def revise_act(feedback_snapshot: str = retry_feedback) -> ActScriptDraft:
                    """Rewrite the bound act with this attempt's feedback."""
                    return writer.run(
                        request,
                        relevant_characters,
                        plan,
                        presentation,
                        chapter,
                        events,
                        notes,
                        original_act.as_draft(),
                        previous_text,
                        anchor_index,
                        feedback_snapshot,
                        promise_brief,
                    )

                candidate = self._call_agent("script_writer", revise_act)
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                attempt_result = ChapterRevisionAttempt(
                    attempt=attempt, status="failed", exception_type=type(exc).__name__
                )
                attempts.append(attempt_result)
                self.repository.save_json(f"{prefix}-validation.json", attempt_result)
                retry_feedback = (
                    "\n\nRETRY CORRECTION:\nThe previous rewrite could not be completed "
                    f"({type(exc).__name__}). Return a complete corrected act."
                )
                continue
            self.repository.save_json(f"{prefix}.json", candidate)
            revised, diagnostic = revision_issue(
                candidate,
                original_act,
                notes,
                chapter=chapter,
                number=chapter_index,
                plan=plan,
                world=world,
                characters=characters,
            )
            attempt_result = ChapterRevisionAttempt(
                attempt=attempt,
                status="accepted" if diagnostic is None else "rejected",
                artifact=f"{prefix}.json",
                diagnostic=diagnostic,
            )
            attempts.append(attempt_result)
            self.repository.save_json(f"{prefix}-validation.json", attempt_result)
            if diagnostic is None:
                final_words = sum(
                    word_count(line.text) for scene in revised.scenes for line in scene.lines
                )
                return revised, ChapterRevisionResult(
                    chapter_id=chapter.id,
                    chapter_index=chapter_index,
                    note_ids=[note.id for note in notes],
                    draft_words=draft_words,
                    attempts=attempts,
                    final_source="revision",
                    final_words=final_words,
                )
            retry_feedback = (
                "\n\nRETRY CORRECTION:\nThe previous rewrite was rejected because "
                f"{diagnostic.message}. {diagnostic.retry_instruction} "
                "Return a complete corrected act."
            )
        warning = (
            f"[SCRIPT_REVISION_REJECTED] Acto {chapter_index}: no hubo una revision valida tras "
            f"{len(attempts)} intentos. Se entrego el acto de {draft_words} palabras."
        )
        self.repository.add_warning(warning)
        self._emit("script_writer_fallback", warning, stage="revision")
        return original_act, ChapterRevisionResult(
            chapter_id=chapter.id,
            chapter_index=chapter_index,
            note_ids=[note.id for note in notes],
            draft_words=draft_words,
            attempts=attempts,
            final_source="draft",
            final_words=draft_words,
            warning_code="SCRIPT_REVISION_REJECTED",
        )

    def _script_frame(
        self,
        request: StoryRequest,
        characters: CharactersArtifact,
        presentation: StoryPresentation,
    ) -> ScriptFrame:
        """Create the printed-script frame for an adapted run, or degrade to default labels."""
        assert self.repository is not None
        adapter = ScriptAdapterAgent(self.provider)

        def create_frame():
            """Create the bound printed-script frame from the finished narrative presentation."""
            return adapter.frame(request, characters, presentation)

        try:
            frame = self._call_agent("script_adapter", create_frame)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception:
            warning = (
                "No se pudieron generar los rotulos del guion; se usan los rotulos por defecto."
            )
            self.repository.add_warning(warning)
            self._emit("script_frame_fallback", warning, stage="adaptation")
            return ScriptFrame(
                cast_heading="Personajes", act_label="Acto", scene_label="Escena", cast=[]
            )
        return normalized_frame(frame, characters)

    def _adapt_story(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        presentation: StoryPresentation,
        bodies: list[str],
        story: str,
        ledger: PromiseLedger | None,
    ) -> PlayScript:
        """Adapt the finished narrative prose into the same theater-script contract."""
        assert self.repository is not None
        self.repository.save_text("prose.md", story)
        self._notify(90, "adaptation", "Adaptando la prosa a guion")
        frame = self._script_frame(request, characters, presentation)
        script_presentation = ScriptPresentation(
            title=presentation.title, chapters=presentation.chapters, frame=frame
        )
        self.repository.save_json("script_presentation.json", script_presentation)
        adapter = ScriptAdapterAgent(self.provider)
        event_by_id = {event.id: event for event in plan.events}
        acts: list[ActScript] = []
        for index, (chapter, body) in enumerate(zip(plan.chapters, bodies, strict=True), 1):
            self._notify(
                90 + (index - 1) * 7 // len(plan.chapters),
                "adaptation",
                f"Adaptando el capitulo {index} de {len(plan.chapters)}",
                index,
                len(plan.chapters),
            )
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            character_ids = {item for event in events for item in event.character_ids}
            relevant = [item for item in characters.characters if item.id in character_ids]
            anchor_index = act_anchor_index(chapter, plan, world, characters)
            previous_act_text = (
                render_act(acts[-1], scene_label=script_presentation.frame.scene_label)
                if acts
                else ""
            )

            def adapt_act(
                feedback: str = "",
                character_snapshot=relevant or characters.characters,
                chapter_snapshot=chapter,
                event_snapshot=events,
                body_snapshot=body,
                previous_snapshot=previous_act_text,
                anchor_snapshot=anchor_index,
            ) -> ActScriptDraft:
                """Adapt one prose chapter with loop values bound to this iteration."""
                return adapter.run(
                    request,
                    world,
                    character_snapshot,
                    plan,
                    presentation,
                    chapter_snapshot,
                    event_snapshot,
                    body_snapshot,
                    previous_snapshot,
                    anchor_snapshot,
                    feedback,
                )

            act = self._act_with_repair(
                agent="script_adapter",
                produce=adapt_act,
                chapter=chapter,
                number=index,
                plan=plan,
                world=world,
                characters=characters,
                directory="adaptation",
                stage="adaptation",
            )
            self.repository.save_json(f"adaptation/act-{index:03d}.json", act)
            acts.append(act)
        self.repository.complete_stage("adaptation")
        return assemble_play(
            script_presentation,
            characters,
            acts,
            language=request.language,
            method=ScriptMethod.ADAPTED,
        )

    def _finalize_script(self, request: StoryRequest, plan: StoryPlan, play: PlayScript) -> None:
        """Persist the structured script, its metrics, and the rendered story.md."""
        assert self.repository is not None
        self.repository.save_json("script.json", play)
        rendered = render_script(play)
        self.repository.save_json(
            "script_metrics.json", script_metrics(request, plan, play, rendered)
        )
        self._publish(rendered, "Guardando el guion", "Guion terminado")
