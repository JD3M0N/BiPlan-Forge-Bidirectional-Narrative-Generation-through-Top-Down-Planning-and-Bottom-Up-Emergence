"""Stage-oriented orchestration for the Top-Down story pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from asg_evaluation import create_evaluation_template

from .agents import (
    AnalystAgent,
    ChapterWriterAgent,
    CharacterDesignerAgent,
    PlotPlannerAgent,
    StoryCriticAgent,
    StoryEditorAgent,
    WorldBuilderAgent,
)
from .audit import audit_chapter, audit_story, canonical_chapter
from .errors import PlotValidationError
from .graph import chapter_word_budgets, materialize_plan
from .progress import PipelineEvent, PipelineEventCallback, ProgressCallback, ProgressUpdate
from .schemas import (
    ChapterLengthAudit,
    CharactersArtifact,
    LLMUsageArtifact,
    StoryPlan,
    StoryRequest,
    WorldArtifact,
)
from .storage import ArtifactRepository

T = TypeVar("T")


class StoryPipeline:
    """Execute one Top-Down request through explicit, testable stages."""

    def __init__(
        self,
        provider,
        output_root: Path,
        default_target_words: int,
        *,
        on_progress: ProgressCallback | None = None,
        on_run_created: Callable[[Path], None] | None = None,
        on_event: PipelineEventCallback | None = None,
    ) -> None:
        """Store pipeline dependencies and optional lifecycle callbacks."""
        self.provider = provider
        self.output_root = Path(output_root)
        self.default_target_words = default_target_words
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
        chapter_count = len(chapter_word_budgets(request))
        self.repository = self._create_repository(request)
        self._configure_provider_callbacks()
        try:
            self._save_request(request)
            world = self._build_world(request)
            characters = self._build_characters(request, world)
            plan = self._build_plan(request, world, characters, chapter_count)
            draft, chapter_audits = self._write_chapters(request, world, characters, plan)
            story = self._review_and_edit(request, plan, draft)
            self._finalize(request, plan, story, chapter_audits)
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
            return AnalystAgent(self.provider, self.default_target_words).run(request)

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
        chapter_count: int,
    ) -> StoryPlan:
        """Generate, validate, and persist a replacement-safe story plan."""
        assert self.repository is not None
        self._notify(38, "planning", "Planificando capítulos y eventos")
        feedback = ""
        validation_errors: list[str] = []
        for attempt in range(1, 3):

            def generate_plan(feedback_snapshot: str = feedback):
                """Generate one plan candidate with feedback bound to this attempt."""
                return PlotPlannerAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    chapter_count,
                    feedback_snapshot,
                )

            draft = self._call_agent(
                "plot_planner",
                generate_plan,
            )
            try:
                plan = materialize_plan(draft, request, world, characters)
            except ValueError as exc:
                feedback = self._record_rejected_plan(draft, attempt, exc, validation_errors)
                continue
            self.repository.save_json("story_plan.json", plan)
            self.repository.complete_stage("planning")
            return plan
        raise PlotValidationError(
            "No se obtuvo un DAG de eventos válido después de dos intentos.",
            details={"attempts": 2, "validation_errors": validation_errors},
            recommendations=["Revisa los intentos guardados bajo planning/."],
        )

    def _record_rejected_plan(
        self,
        draft,
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
        return (
            "\n\nRETURN A COMPLETE REPLACEMENT PLAN. Fix this structural error: "
            f"{issue}. Previous candidate:\n{draft.model_dump_json(indent=2)}"
        )

    def _write_chapters(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
    ) -> tuple[str, list[ChapterLengthAudit]]:
        """Write every planned chapter and return the assembled draft."""
        assert self.repository is not None
        writer = ChapterWriterAgent(self.provider)
        event_by_id = {item.id: item for item in plan.events}
        bodies: list[str] = []
        audits: list[ChapterLengthAudit] = []
        for index, chapter in enumerate(plan.chapters, 1):
            self._notify_chapter(index, len(plan.chapters))
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            character_ids = {item for event in events for item in event.character_ids}
            relevant = [item for item in characters.characters if item.id in character_ids]

            def write_chapter(
                character_snapshot=relevant or characters.characters,
                chapter_snapshot=chapter,
                event_snapshot=events,
                previous_body: str = bodies[-1] if bodies else "",
            ):
                """Write one chapter with loop values bound to this iteration."""
                return writer.run(
                    request,
                    world,
                    character_snapshot,
                    plan,
                    chapter_snapshot,
                    event_snapshot,
                    previous_body,
                )

            body = self._call_agent(
                "chapter_writer",
                write_chapter,
            ).strip()
            self.repository.save_text(f"chapters/chapter-{index:03d}.md", body)
            bodies.append(body)
            audits.append(audit_chapter(chapter, body))
        self.repository.complete_stage("writing")
        draft = f"# {request.title}\n\n" + "\n\n".join(
            canonical_chapter(chapter.title, body)
            for chapter, body in zip(plan.chapters, bodies, strict=True)
        )
        self.repository.save_text("draft.md", draft)
        return draft, audits

    def _notify_chapter(self, index: int, total: int) -> None:
        """Report progress for the chapter currently being written."""
        percent = 50 + (index - 1) * 30 // total
        self._notify(
            percent,
            "writing",
            f"Escribiendo capítulo {index} de {total}",
            index,
            total,
        )

    def _review_and_edit(self, request: StoryRequest, plan: StoryPlan, draft: str) -> str:
        """Run the optional quality pass and safely fall back to the draft."""
        assert self.repository is not None
        self._notify(85, "review", "Revisando el borrador completo")
        try:

            def review_story():
                """Review the bound complete story draft."""
                return StoryCriticAgent(self.provider).run(request, plan, draft)

            review = self._call_agent("story_critic", review_story)
            self.repository.save_json("review.json", review)
            self.repository.complete_stage("review")
            self._notify(92, "editing", "Aplicando una edición final")

            def edit_story():
                """Edit the bound draft using its completed review."""
                return StoryEditorAgent(self.provider).run(request, plan, draft, review)

            story = self._call_agent("story_editor", edit_story).strip()
            self.repository.complete_stage("editing")
            return story
        except Exception as exc:
            warning = (
                "La revisión o edición final no pudo completarse; se entregó el borrador "
                f"por capítulos ({type(exc).__name__})."
            )
            self.repository.add_warning(warning)
            self._emit("quality_fallback", warning, stage=self.progress["stage"])
            return draft

    def _finalize(
        self,
        request: StoryRequest,
        plan: StoryPlan,
        story: str,
        chapter_audits: list[ChapterLengthAudit],
    ) -> None:
        """Persist final audits, evaluation template, metadata, and story."""
        assert self.repository is not None
        self.repository.save_json(
            "length_audit.json",
            audit_story(request, plan, story, chapter_audits),
        )
        self._notify(98, "saving", "Guardando la historia")
        self.repository.save_text("story.md", story)
        create_evaluation_template(self.repository.run_dir)
        self.repository.complete_stage("story")
        self._save_usage()
        self.repository.complete()
        self._notify(100, "completed", "Historia terminada")

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
