"""Stage-oriented orchestration for the Top-Down story pipeline."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from asg_core import AudioGenerationError, create_story_audio_sync
from asg_evaluation import create_evaluation_template

from .agents import (
    AnalystAgent,
    CharacterDesignerAgent,
    DrafterAgent,
    DramaCriticAgent,
    PlanCriticAgent,
    PlotPlannerAgent,
    WorldBuilderAgent,
    WriterAgent,
)
from .audit import canonical_chapter, story_metrics, word_count
from .errors import PlotValidationError
from .graph import materialize_plan, relevant_prior_events, validate_profile_structure
from .progress import PipelineEvent, PipelineEventCallback, ProgressCallback, ProgressUpdate
from .schemas import (
    ChapterPlan,
    ChapterRevisionAttempt,
    ChapterRevisionResult,
    CharactersArtifact,
    LLMUsageArtifact,
    PlotEvent,
    RevisionNote,
    RevisionReport,
    StoryPlan,
    StoryPlanDraft,
    StoryPresentation,
    StoryRequest,
    StoryReview,
    WorldArtifact,
    WriterCandidateDiagnostic,
)
from .storage import ArtifactRepository

T = TypeVar("T")


class StoryPipeline:
    """Execute one Top-Down request through explicit, testable stages."""

    def __init__(
        self,
        provider,
        output_root: Path,
        *,
        on_progress: ProgressCallback | None = None,
        on_run_created: Callable[[Path], None] | None = None,
        on_event: PipelineEventCallback | None = None,
    ) -> None:
        """Store pipeline dependencies and optional lifecycle callbacks."""
        self.provider = provider
        self.output_root = Path(output_root)
        self.on_progress = on_progress
        self.on_run_created = on_run_created
        self.on_event = on_event
        self.progress = {"percent": 0, "stage": "analysis"}
        self.usage_start = 0
        self.repository: ArtifactRepository | None = None

    def execute(self, request: StoryRequest | str) -> Path:
        """Run all story stages and return the completed run directory."""
        self.usage_start = len(getattr(self.provider, "usage_records", []))
        request = self._analyze_request(request)
        self.repository = self._create_repository(request)
        self._configure_provider_callbacks()
        try:
            self._save_request(request)
            world = self._build_world(request)
            characters = self._build_characters(request, world)
            plan = self._build_plan(request, world, characters)
            presentation, draft_bodies, draft = self._draft_chapters(
                request,
                world,
                characters,
                plan,
            )
            story = self._critique_and_revise(
                request,
                world,
                characters,
                plan,
                presentation,
                draft_bodies,
                draft,
            )
            self._finalize(request, plan, story)
            return self.repository.run_dir
        except Exception as exc:
            self._record_failure(exc)
            raise
        finally:
            self._clear_provider_callbacks()

    def _analyze_request(self, request: StoryRequest | str) -> StoryRequest:
        """Convert a free-form prompt into a validated story request."""
        self._notify(0, "analysis", "Analizando la solicitud")
        if isinstance(request, StoryRequest):
            return request

        def analyze_request():
            """Analyze the bound free-form request into a story contract."""
            return AnalystAgent(self.provider).run(request)

        return self._call_agent("analyst", analyze_request)

    def _create_repository(self, request: StoryRequest) -> ArtifactRepository:
        """Create the run repository and attach artifact event reporting."""
        repository = ArtifactRepository(
            self.output_root,
            self.provider.model_name,
            request.title,
            on_artifact=self._report_artifact,
        )
        if self.on_run_created:
            self.on_run_created(repository.run_dir)
        for record in list(getattr(self.provider, "usage_records", []))[self.usage_start :]:
            repository.append_llm_call(record)
        return repository

    def _report_artifact(self, filename: str, created: bool) -> None:
        """Emit a structured event when an artifact is written."""
        self._emit(
            "artifact_created" if created else "artifact_updated",
            f"artefacto {filename} {'creado' if created else 'actualizado'}",
            stage=self.progress["stage"],
            artifact=filename,
        )

    def _report_wait(self, seconds: int, reason: str) -> None:
        """Report provider quota waits through the pipeline progress channel."""
        self._notify(
            self.progress["percent"],
            "rate_limit",
            f"Esperando cuota: {seconds}s ({reason})",
        )

    def _configure_provider_callbacks(self) -> None:
        """Route provider quota and usage events into pipeline callbacks."""
        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = self._report_wait
        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = self._record_usage

    def _clear_provider_callbacks(self) -> None:
        """Detach per-run provider callbacks after completion or failure."""
        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = None
        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = None

    def _record_usage(self, record) -> None:
        """Persist one provider usage record and refresh the aggregate."""
        assert self.repository is not None
        self.repository.append_llm_call(record)
        self._save_usage()

    def _usage_artifact(self) -> LLMUsageArtifact:
        """Aggregate provider usage produced by the current run."""
        records = list(getattr(self.provider, "usage_records", []))[self.usage_start :]
        return LLMUsageArtifact(
            records=records,
            calls=len(records),
            failed_calls=sum(item.status == "failed" for item in records),
            total_tokens=sum(item.total_tokens for item in records),
            total_wait_seconds=sum(item.wait_seconds for item in records),
        )

    def _save_usage(self) -> None:
        """Write the current aggregate LLM usage artifact."""
        assert self.repository is not None
        self.repository.save_json("llm_usage.json", self._usage_artifact())

    def _save_request(self, request: StoryRequest) -> None:
        """Persist the analyzed request and complete the analysis stage."""
        assert self.repository is not None
        self.repository.save_json("request.json", request)
        self.repository.complete_stage("analysis")

    def _build_world(self, request: StoryRequest) -> WorldArtifact:
        """Generate and persist the story world artifact."""
        assert self.repository is not None
        self._notify(12, "world", "Construyendo el mundo")

        def build_world():
            """Generate the world for the bound story request."""
            return WorldBuilderAgent(self.provider).run(request)

        world = self._call_agent("world", build_world)
        self.repository.save_json("world.json", world)
        self.repository.complete_stage("world")
        return world

    def _build_characters(
        self,
        request: StoryRequest,
        world: WorldArtifact,
    ) -> CharactersArtifact:
        """Generate and persist the story character artifact."""
        assert self.repository is not None
        self._notify(25, "characters", "Diseñando los personajes")

        def build_characters():
            """Generate characters for the bound request and world."""
            return CharacterDesignerAgent(self.provider).run(request, world)

        characters = self._call_agent("characters", build_characters)
        self.repository.save_json("characters.json", characters)
        self.repository.complete_stage("characters")
        return characters

    def _build_plan(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
    ) -> StoryPlan:
        """Generate, validate, critique, and optionally refine the story plan."""
        assert self.repository is not None
        self._notify(38, "planning", "Planificando capítulos y eventos")
        feedback = ""
        validation_errors: list[str] = []
        plan: StoryPlan | None = None
        for attempt in range(1, 3):

            def generate_plan(feedback_snapshot: str = feedback):
                """Generate one plan candidate with feedback bound to this attempt."""
                return PlotPlannerAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    feedback_snapshot,
                )

            draft = self._call_agent(
                "plot_planner",
                generate_plan,
            )
            try:
                plan = materialize_plan(draft, world, characters)
                validate_profile_structure(plan, request.narrative_profile)
            except ValueError as exc:
                plan = None
                feedback = self._record_rejected_plan(draft, attempt, exc, validation_errors)
                continue
            break
        if plan is None:
            raise PlotValidationError(
                "No se obtuvo un DAG de eventos válido después de dos intentos.",
                details={"attempts": 2, "validation_errors": validation_errors},
                recommendations=["Revisa los intentos guardados bajo planning/."],
            )
        plan = self._critique_plan(request, world, characters, plan)
        self.repository.save_json("story_plan.json", plan)
        self.repository.complete_stage("planning")
        return plan

    def _critique_plan(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        original_plan: StoryPlan,
    ) -> StoryPlan:
        """Apply one bounded plan-critique round without risking a valid plan."""
        assert self.repository is not None
        self._notify(46, "plan_review", "Revisando la calidad dramática del plan")
        try:

            def critique_plan():
                """Critique the bound validated plan."""
                return PlanCriticAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    original_plan,
                )

            review = self._call_agent("plan_critic", critique_plan)
            self.repository.save_json("plan_review.json", review)
            self._validate_note_references(review.notes, original_plan)
            self.repository.complete_stage("plan_review")
            if review.approved:
                return original_plan

            def refine_plan():
                """Return one complete plan replacement guided by the critique."""
                return PlotPlannerAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    plan_review=review,
                )

            candidate = self._call_agent("plot_planner", refine_plan)
            self.repository.save_json("planning/refined-candidate.json", candidate)
            try:
                refined = materialize_plan(candidate, world, characters)
                validate_profile_structure(refined, request.narrative_profile)
            except ValueError as exc:
                issue = str(exc).strip() or type(exc).__name__
                self.repository.save_data(
                    "planning/refined-candidate-validation.json",
                    {"issue": issue},
                )
                warning = (
                    "La revisión del plan produjo un reemplazo estructuralmente inválido; "
                    "se conservó el primer plan válido."
                )
                self.repository.add_warning(warning)
                self._emit("plan_refinement_fallback", warning, stage="plan_review")
                return original_plan
            self._emit("plan_refined", "plan refinado tras la crítica", stage="plan_review")
            return refined
        except Exception as exc:
            warning = (
                "La crítica del plan no pudo completarse; se conservó el primer plan "
                f"estructuralmente válido ({type(exc).__name__})."
            )
            self.repository.add_warning(warning)
            self._emit("plan_review_fallback", warning, stage="plan_review")
            self.repository.complete_stage("plan_review")
            return original_plan

    def _record_rejected_plan(
        self,
        draft: StoryPlanDraft,
        attempt: int,
        error: ValueError,
        validation_errors: list[str],
    ) -> str:
        """Persist one rejected plan and return feedback for its replacement."""
        assert self.repository is not None
        issue = str(error).strip() or type(error).__name__
        validation_errors.append(issue)
        prefix = f"planning/attempt-{attempt:03d}"
        self.repository.save_json(f"{prefix}.json", draft)
        self.repository.save_data(
            f"{prefix}-validation.json",
            {"attempt": attempt, "issue": issue},
        )
        self._emit(
            "plan_rejected",
            f"plan rechazado: {issue}",
            stage="planning",
            attempt=attempt,
        )
        payoff_rules = self._payoff_reference_rules(draft)
        return (
            "\n\nSTRUCTURAL REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT PLAN. "
            f"Fix this structural error: {issue}. "
            "For payoff_of, use only an exact event_id listed in allowed_earlier_event_ids "
            "for that event. Never copy object IDs, character IDs, location IDs, names, or "
            "prose into payoff_of; use [] when there is no valid earlier setup.\n"
            f"PAYOFF_OF REFERENCE MATRIX:\n{payoff_rules}\n"
            f"REJECTED CANDIDATE:\n{draft.model_dump_json(indent=2)}"
        )

    @staticmethod
    def _payoff_reference_rules(draft: StoryPlanDraft) -> str:
        """Describe the exact payoff references allowed by one rejected candidate."""
        ordered = sorted(draft.events, key=lambda event: event.order)
        rules = [
            {
                "event_id": event.id,
                "current_payoff_of": event.payoff_of,
                "allowed_earlier_event_ids": [
                    candidate.id for candidate in ordered if candidate.order < event.order
                ],
            }
            for event in ordered
        ]
        return json.dumps(rules, ensure_ascii=False, indent=2)

    def _draft_chapters(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
    ) -> tuple[StoryPresentation, list[str], str]:
        """Use Drafter to localize titles and create the first story."""
        assert self.repository is not None
        drafter = DrafterAgent(self.provider)

        def create_presentation():
            """Create localized story and chapter titles."""
            return drafter.presentation(request, plan)

        presentation = self._call_agent("drafter", create_presentation)
        self._validate_presentation(plan, presentation)
        self.repository.save_json("draft_presentation.json", presentation)
        event_by_id = {item.id: item for item in plan.events}
        bodies: list[str] = []
        for index, chapter in enumerate(plan.chapters, 1):
            self._notify_draft_chapter(index, len(plan.chapters))
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            history = relevant_prior_events(plan, {event.id for event in events})
            character_ids = {item for event in events for item in event.character_ids}
            relevant = [item for item in characters.characters if item.id in character_ids]

            def draft_chapter(
                character_snapshot=relevant or characters.characters,
                chapter_snapshot=chapter,
                event_snapshot=events,
                history_snapshot=history,
                previous_body: str = bodies[-1] if bodies else "",
            ):
                """Draft one chapter with loop values bound to this iteration."""
                return drafter.run(
                    request,
                    world,
                    character_snapshot,
                    plan,
                    presentation,
                    chapter_snapshot,
                    event_snapshot,
                    history_snapshot,
                    previous_body,
                )

            body = self._call_agent("drafter", draft_chapter).strip()
            self.repository.save_text(f"chapters/chapter-{index:03d}.md", body)
            bodies.append(body)
        self.repository.complete_stage("drafting")
        draft = self._assemble_story(plan, presentation, bodies)
        self.repository.save_text("draft.md", draft)
        return presentation, bodies, draft

    @staticmethod
    def _validate_presentation(plan: StoryPlan, presentation: StoryPresentation) -> None:
        """Require one localized title for every canonical chapter, in order."""
        expected = [chapter.id for chapter in plan.chapters]
        received = [chapter.chapter_id for chapter in presentation.chapters]
        if received != expected:
            raise ValueError("localized presentation must follow the canonical chapter order")

    @staticmethod
    def _assemble_story(
        plan: StoryPlan,
        presentation: StoryPresentation,
        bodies: list[str],
    ) -> str:
        """Assemble canonical Markdown without delegating ordering to an LLM."""
        titles = {chapter.chapter_id: chapter.title for chapter in presentation.chapters}
        return f"# {presentation.title}\n\n" + "\n\n".join(
            canonical_chapter(titles[chapter.id], body)
            for chapter, body in zip(plan.chapters, bodies, strict=True)
        )

    def _notify_draft_chapter(self, index: int, total: int) -> None:
        """Report progress for the chapter currently being drafted."""
        percent = 52 + (index - 1) * 24 // total
        self._notify(
            percent,
            "drafting",
            f"Redactando borrador del capítulo {index} de {total}",
            index,
            total,
        )

    def _critique_and_revise(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        presentation: StoryPresentation,
        draft_bodies: list[str],
        draft: str,
    ) -> str:
        """Critique the complete draft, then let Writer revise chapter by chapter."""
        assert self.repository is not None
        self._notify(78, "critique", "Analizando el drama del borrador completo")
        try:

            def critique_story():
                """Critique the bound complete story draft."""
                return DramaCriticAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    plan,
                    presentation,
                    draft,
                )

            review = self._call_agent("drama_critic", critique_story)
            self.repository.save_json("review.json", review)
            self._validate_note_references(review.notes, plan)
            self.repository.complete_stage("critique")
        except Exception as exc:
            warning = (
                "La crítica dramática no pudo completarse; se entregó el borrador "
                f"por capítulos ({type(exc).__name__})."
            )
            self.repository.add_warning(warning)
            self._emit("quality_fallback", warning, stage=self.progress["stage"])
            return draft
        return self._revise_chapters(
            request,
            plan,
            presentation,
            draft_bodies,
            review,
        )

    @staticmethod
    def _validate_note_references(notes: list[RevisionNote], plan: StoryPlan) -> None:
        """Reject critic notes that point outside the canonical plan."""
        chapter_ids = {chapter.id for chapter in plan.chapters}
        event_ids = {event.id for event in plan.events}
        for note in notes:
            if set(note.chapter_ids) - chapter_ids:
                raise ValueError(f"revision note {note.id} references unknown chapters")
            if set(note.event_ids) - event_ids:
                raise ValueError(f"revision note {note.id} references unknown events")

    def _revise_chapters(
        self,
        request: StoryRequest,
        plan: StoryPlan,
        presentation: StoryPresentation,
        draft_bodies: list[str],
        review: StoryReview,
    ) -> str:
        """Run Writer for every chapter with one bounded corrective retry."""
        assert self.repository is not None
        writer = WriterAgent(self.provider)
        event_by_id = {event.id: event for event in plan.events}
        revised_bodies: list[str] = []
        revision_results: list[ChapterRevisionResult] = []
        for index, (chapter, draft_body) in enumerate(
            zip(plan.chapters, draft_bodies, strict=True),
            1,
        ):
            percent = 84 + (index - 1) * 12 // len(plan.chapters)
            self._notify(
                percent,
                "revision",
                f"Corrigiendo capítulo {index} de {len(plan.chapters)}",
                index,
                len(plan.chapters),
            )
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            notes = self._notes_for_chapter(review.notes, chapter, events)
            accepted, result = self._revise_one_chapter(
                writer,
                request,
                plan,
                presentation,
                chapter,
                events,
                notes,
                draft_body,
                revised_bodies[-1] if revised_bodies else "",
                index,
            )
            revised_bodies.append(accepted)
            revision_results.append(result)
            self.repository.save_text(f"revisions/chapter-{index:03d}.md", accepted)
            self.repository.save_json(
                "revision_report.json",
                RevisionReport(chapters=revision_results),
            )
        self.repository.complete_stage("revision")
        return self._assemble_story(plan, presentation, revised_bodies)

    @staticmethod
    def _notes_for_chapter(
        notes: list[RevisionNote],
        chapter: ChapterPlan,
        events: list[PlotEvent],
    ) -> list[RevisionNote]:
        """Select global notes and notes that target this chapter or its events."""
        event_ids = {event.id for event in events}
        return [
            note
            for note in notes
            if (
                not note.chapter_ids
                or chapter.id in note.chapter_ids
                or bool(event_ids.intersection(note.event_ids))
            )
        ]

    def _revise_one_chapter(
        self,
        writer: WriterAgent,
        request: StoryRequest,
        plan: StoryPlan,
        presentation: StoryPresentation,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        notes: list[RevisionNote],
        draft_body: str,
        previous_revised: str,
        chapter_index: int,
    ) -> tuple[str, ChapterRevisionResult]:
        """Return the first valid Writer candidate or the safe original fallback."""
        assert self.repository is not None
        draft_words = word_count(draft_body)
        attempts: list[ChapterRevisionAttempt] = []
        retry_feedback = ""
        for attempt in range(1, 3):
            prefix = f"writer/chapter-{chapter_index:03d}-attempt-{attempt:03d}"
            try:

                def revise_chapter(feedback_snapshot: str = retry_feedback):
                    """Rewrite the bound chapter with this attempt's feedback."""
                    return writer.run(
                        request,
                        plan,
                        presentation,
                        chapter,
                        events,
                        notes,
                        draft_body,
                        previous_revised,
                        feedback_snapshot,
                    )

                candidate = self._call_agent("writer", revise_chapter).strip()
            except Exception as exc:
                attempt_result = ChapterRevisionAttempt(
                    attempt=attempt,
                    status="failed",
                    exception_type=type(exc).__name__,
                )
                attempts.append(attempt_result)
                self.repository.save_json(f"{prefix}-validation.json", attempt_result)
                warning = (
                    "[WRITER_REVISION_REJECTED] Writer no pudo corregir el capítulo "
                    f"{chapter_index}; el intento {attempt} falló con "
                    f"{type(exc).__name__} y se conservó el borrador de {draft_words} "
                    "palabras."
                )
                self.repository.add_warning(warning)
                self._emit("writer_fallback", warning, stage="revision")
                return draft_body, ChapterRevisionResult(
                    chapter_id=chapter.id,
                    chapter_index=chapter_index,
                    note_ids=[note.id for note in notes],
                    draft_words=draft_words,
                    attempts=attempts,
                    final_source="draft",
                    final_words=draft_words,
                    warning_code="WRITER_REVISION_REJECTED",
                )
            self.repository.save_text(f"{prefix}.md", candidate)
            diagnostic = self._writer_candidate_issue(candidate, draft_body, notes)
            attempt_result = ChapterRevisionAttempt(
                attempt=attempt,
                status="accepted" if diagnostic is None else "rejected",
                artifact=f"{prefix}.md",
                diagnostic=diagnostic,
            )
            attempts.append(attempt_result)
            self.repository.save_json(f"{prefix}-validation.json", attempt_result)
            if diagnostic is None:
                return candidate, ChapterRevisionResult(
                    chapter_id=chapter.id,
                    chapter_index=chapter_index,
                    note_ids=[note.id for note in notes],
                    draft_words=draft_words,
                    attempts=attempts,
                    final_source="revision",
                    final_words=word_count(candidate),
                )
            retry_feedback = (
                "\n\nRETRY CORRECTION:\nThe previous rewrite was rejected because "
                f"{diagnostic.message}. {diagnostic.retry_instruction} "
                "Return a complete corrected chapter body."
            )
        warning = self._writer_fallback_warning(chapter_index, draft_words, attempts)
        self.repository.add_warning(warning)
        self._emit("writer_fallback", warning, stage="revision")
        return draft_body, ChapterRevisionResult(
            chapter_id=chapter.id,
            chapter_index=chapter_index,
            note_ids=[note.id for note in notes],
            draft_words=draft_words,
            attempts=attempts,
            final_source="draft",
            final_words=draft_words,
            warning_code="WRITER_REVISION_REJECTED",
        )

    @staticmethod
    def _writer_candidate_issue(
        candidate: str,
        draft_body: str,
        notes: list[RevisionNote],
    ) -> WriterCandidateDiagnostic | None:
        """Explain why a Writer candidate cannot replace the draft."""
        actual_words = word_count(candidate)
        if not candidate.strip():
            return WriterCandidateDiagnostic(
                code="EMPTY_CHAPTER_BODY",
                message="the chapter body is empty",
                retry_instruction="Write a complete chapter body that fulfills the planned events.",
                actual_words=actual_words,
            )
        if any(line.lstrip().startswith("#") for line in candidate.splitlines()):
            return WriterCandidateDiagnostic(
                code="MARKDOWN_HEADINGS",
                message="the chapter body contains Markdown headings",
                retry_instruction="Remove every Markdown heading while preserving the prose body.",
                actual_words=actual_words,
            )
        significant = any(note.priority in {"critical", "major"} for note in notes)
        if significant and candidate.strip() == draft_body.strip():
            return WriterCandidateDiagnostic(
                code="UNCHANGED_SIGNIFICANT_NOTES",
                message="the text is unchanged despite critical or major revision notes",
                retry_instruction="Apply every critical and major note with visible prose changes.",
                actual_words=actual_words,
            )
        return None

    @staticmethod
    def _writer_fallback_warning(
        chapter_index: int,
        draft_words: int,
        attempts: list[ChapterRevisionAttempt],
    ) -> str:
        """Build a concise Spanish warning from the structured rejection trail."""
        diagnostics = [item.diagnostic for item in attempts if item.diagnostic is not None]
        codes = ", ".join(item.code for item in diagnostics) or "WRITER_EXCEPTION"
        return (
            "[WRITER_REVISION_REJECTED] Capítulo "
            f"{chapter_index}: no hubo una revisión válida tras {len(attempts)} intentos "
            f"({codes}). Se entregó el borrador de {draft_words} palabras."
        )

    def _finalize(
        self,
        request: StoryRequest,
        plan: StoryPlan,
        story: str,
    ) -> None:
        """Persist observed metrics, evaluation template, metadata, and story."""
        assert self.repository is not None
        self.repository.save_json(
            "story_metrics.json",
            story_metrics(request, plan, story),
        )
        self._notify(98, "saving", "Guardando la historia")
        self.repository.save_text("story.md", story)
        create_evaluation_template(self.repository.run_dir)
        self.repository.complete_stage("story")
        self._create_audio()
        self._save_usage()
        self.repository.complete()
        self._notify(100, "completed", "Historia terminada")

    def _create_audio(self) -> None:
        """Create optional narration without invalidating a completed story."""
        assert self.repository is not None
        self._notify(99, "audio", "Generando narraci?n de la historia")
        try:
            create_story_audio_sync(self.repository.run_dir / "story.md")
        except AudioGenerationError:
            self.repository.add_warning(
                "[AUDIO_GENERATION_FAILED] No se pudo crear story.mp3; story.md permanece v?lido."
            )
        else:
            self.repository.register_existing("story.mp3")
            self.repository.complete_stage("audio")
        if (self.repository.run_dir / "audio.json").is_file():
            self.repository.register_existing("audio.json")

    def _record_failure(self, error: Exception) -> None:
        """Persist a failed pipeline outcome before re-raising the error."""
        assert self.repository is not None
        stage = getattr(error, "stage", self.progress["stage"])
        summary = getattr(error, "summary", type(error).__name__)
        self._emit("pipeline_failed", f"fallo la etapa {stage}: {summary}", stage=stage)
        self._save_usage()
        self.repository.fail(error)

    def _call_agent(self, name: str, function: Callable[[], T]) -> T:
        """Emit an agent event and execute the supplied agent operation."""
        self._emit("agent_called", f"se llamo al agente {name}", stage=self.progress["stage"])
        return function()

    def _notify(
        self,
        percent: int,
        stage: str,
        description: str,
        chapter: int | None = None,
        total: int | None = None,
    ) -> None:
        """Update internal progress and invoke the external progress callback."""
        if stage != "rate_limit":
            self.progress.update(percent=percent, stage=stage)
        if self.on_progress:
            self.on_progress(ProgressUpdate(percent, stage, description, chapter, total))

    def _emit(
        self,
        kind: str,
        message: str,
        *,
        stage: str | None = None,
        chapter_id: str | None = None,
        attempt: int | None = None,
        artifact: str | None = None,
    ) -> None:
        """Publish a structured pipeline event when a callback is configured."""
        if self.on_event:
            self.on_event(
                PipelineEvent(
                    kind=kind,
                    message=message,
                    stage=stage,
                    chapter_id=chapter_id,
                    attempt=attempt,
                    artifact=artifact,
                )
            )
