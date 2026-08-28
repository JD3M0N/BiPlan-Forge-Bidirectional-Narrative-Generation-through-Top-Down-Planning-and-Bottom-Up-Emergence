"""Small, explicit orchestration for Top-Down 5.0."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Callable, TypeVar

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
from .errors import PlotValidationError
from .graph import chapter_word_budgets, materialize_plan
from .progress import (
    PipelineEvent,
    PipelineEventCallback,
    ProgressCallback,
    ProgressUpdate,
)
from .schemas import (
    ChapterLengthAudit,
    LengthAuditArtifact,
    LengthAuditEntry,
    LLMUsageArtifact,
    StoryPlan,
    StoryRequest,
)
from .storage import ArtifactRepository


T = TypeVar("T")


def _word_count(text: str) -> int:
    return len(text.split())


def _bounds(target: int) -> tuple[int, int]:
    return math.floor(target * 0.90), math.ceil(target * 1.20)


def _canonical_chapter(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}"


def _parse_chapter_bodies(story: str, expected: int) -> list[str]:
    """Recover edited chapter bodies when all Markdown headings were preserved."""
    headings = list(re.finditer(r"(?m)^##\s+.+$", story))
    if len(headings) != expected:
        return []
    return [
        story[heading.end():(headings[index + 1].start() if index + 1 < expected else None)].strip()
        for index, heading in enumerate(headings)
    ]


class StoryRun:
    """A completed Top-Down 5.0 run."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        metadata_path = self.run_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("status") != "completed" or metadata.get("pipeline_version") != "5.0":
            raise ValueError("Only completed Top-Down 5.0 runs can be opened as StoryRun")

    @property
    def story_path(self) -> Path:
        return self.run_dir / "story.md"

    def __fspath__(self) -> str:
        return str(self.run_dir)


class StoryGenerator:
    """Public Top-Down 5.0 generator."""

    def __init__(
        self, provider, output_root: Path, default_target_words: int = 1500,
    ) -> None:
        if not 300 <= default_target_words <= 20_000:
            raise ValueError("default_target_words must be between 300 and 20000")
        self.provider = provider
        self.output_root = Path(output_root)
        self.default_target_words = default_target_words

    @staticmethod
    def _usage_artifact(provider, start: int) -> LLMUsageArtifact:
        records = list(getattr(provider, "usage_records", []))[start:]
        return LLMUsageArtifact(
            records=records,
            calls=len(records),
            failed_calls=sum(item.status == "failed" for item in records),
            total_tokens=sum(item.total_tokens for item in records),
            total_wait_seconds=sum(item.wait_seconds for item in records),
        )

    def generate(
        self,
        request: StoryRequest | str,
        on_progress: ProgressCallback | None = None,
        on_run_created=None,
        on_event: PipelineEventCallback | None = None,
    ) -> StoryRun:
        progress = {"percent": 0, "stage": "analysis"}

        def emit(
            kind: str,
            message: str,
            *,
            stage: str | None = None,
            chapter_id: str | None = None,
            attempt: int | None = None,
            artifact: str | None = None,
        ) -> None:
            if on_event:
                on_event(PipelineEvent(
                    kind=kind,
                    message=message,
                    stage=stage,
                    chapter_id=chapter_id,
                    attempt=attempt,
                    artifact=artifact,
                ))

        def notify(
            percent: int,
            stage: str,
            description: str,
            chapter: int | None = None,
            total: int | None = None,
        ) -> None:
            if stage != "rate_limit":
                progress.update(percent=percent, stage=stage)
            if on_progress:
                on_progress(ProgressUpdate(percent, stage, description, chapter, total))

        def call_agent(name: str, function: Callable[[], T]) -> T:
            emit("agent_called", f"se llamo al agente {name}", stage=progress["stage"])
            return function()

        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = lambda seconds, reason: notify(
                progress["percent"],
                "rate_limit",
                f"Esperando cuota: {seconds}s ({reason})",
            )
        usage_start = len(getattr(self.provider, "usage_records", []))
        notify(0, "analysis", "Analizando la solicitud")
        if isinstance(request, str):
            request = call_agent(
                "analyst",
                lambda: AnalystAgent(self.provider, self.default_target_words).run(request),
            )
        budgets = chapter_word_budgets(request)
        repository = ArtifactRepository(
            self.output_root,
            self.provider.model_name,
            request.title,
            on_artifact=lambda filename, created: emit(
                "artifact_created" if created else "artifact_updated",
                f"artefacto {filename} {'creado' if created else 'actualizado'}",
                stage=progress["stage"],
                artifact=filename,
            ),
        )
        if on_run_created:
            on_run_created(repository.run_dir)
        for record in list(getattr(self.provider, "usage_records", []))[usage_start:]:
            repository.append_llm_call(record)

        def save_usage() -> None:
            repository.save_json(
                "llm_usage.json", self._usage_artifact(self.provider, usage_start),
            )

        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = lambda record: (
                repository.append_llm_call(record), save_usage(),
            )

        try:
            repository.save_json("request.json", request)
            repository.complete_stage("analysis")

            notify(12, "world", "Construyendo el mundo")
            world = call_agent("world", lambda: WorldBuilderAgent(self.provider).run(request))
            repository.save_json("world.json", world)
            repository.complete_stage("world")

            notify(25, "characters", "Diseñando los personajes")
            characters = call_agent(
                "characters",
                lambda: CharacterDesignerAgent(self.provider).run(request, world),
            )
            repository.save_json("characters.json", characters)
            repository.complete_stage("characters")

            notify(38, "planning", "Planificando capítulos y eventos")
            feedback = ""
            validation_errors: list[str] = []
            plan: StoryPlan | None = None
            for attempt in range(1, 3):
                draft = call_agent(
                    "plot_planner",
                    lambda: PlotPlannerAgent(self.provider).run(
                        request, world, characters, len(budgets), feedback,
                    ),
                )
                try:
                    plan = materialize_plan(draft, request, world, characters)
                    break
                except ValueError as exc:
                    issue = str(exc).strip() or type(exc).__name__
                    validation_errors.append(issue)
                    prefix = f"planning/attempt-{attempt:03d}"
                    repository.save_json(f"{prefix}.json", draft)
                    repository.save_data(f"{prefix}-validation.json", {
                        "attempt": attempt,
                        "issue": issue,
                    })
                    emit(
                        "plan_rejected",
                        f"plan rechazado: {issue}",
                        stage="planning",
                        attempt=attempt,
                    )
                    feedback = (
                        "\n\nRETURN A COMPLETE REPLACEMENT PLAN. Fix this structural error: "
                        f"{issue}. Previous candidate:\n{draft.model_dump_json(indent=2)}"
                    )
            if plan is None:
                raise PlotValidationError(
                    "No se obtuvo un DAG de eventos válido después de dos intentos.",
                    details={"attempts": 2, "validation_errors": validation_errors},
                    recommendations=["Revisa los intentos guardados bajo planning/."],
                )
            repository.save_json("story_plan.json", plan)
            repository.complete_stage("planning")

            writer = ChapterWriterAgent(self.provider)
            event_by_id = {item.id: item for item in plan.events}
            chapter_bodies: list[str] = []
            chapter_audits: list[ChapterLengthAudit] = []
            total_chapters = len(plan.chapters)
            for index, chapter in enumerate(plan.chapters, 1):
                percent = 50 + (index - 1) * 30 // total_chapters
                notify(
                    percent,
                    "writing",
                    f"Escribiendo capítulo {index} de {total_chapters}",
                    index,
                    total_chapters,
                )
                events = [
                    event_by_id[identifier]
                    for identifier in plan.topological_order
                    if event_by_id[identifier].chapter_id == chapter.id
                ]
                character_ids = {
                    identifier for event in events for identifier in event.character_ids
                }
                relevant_characters = [
                    item for item in characters.characters if item.id in character_ids
                ] or characters.characters
                body = call_agent(
                    "chapter_writer",
                    lambda: writer.run(
                        request,
                        world,
                        relevant_characters,
                        plan,
                        chapter,
                        events,
                        chapter_bodies[-1] if chapter_bodies else "",
                    ),
                ).strip()
                repository.save_text(f"chapters/chapter-{index:03d}.md", body)
                chapter_bodies.append(body)
                minimum, maximum = _bounds(chapter.target_words)
                actual = _word_count(body)
                chapter_audits.append(ChapterLengthAudit(
                    chapter_id=chapter.id,
                    target_words=chapter.target_words,
                    minimum_words=minimum,
                    maximum_words=maximum,
                    actual_words=actual,
                    within_tolerance=minimum <= actual <= maximum,
                ))
            repository.complete_stage("writing")
            draft = f"# {request.title}\n\n" + "\n\n".join(
                _canonical_chapter(chapter.title, body)
                for chapter, body in zip(plan.chapters, chapter_bodies)
            )
            repository.save_text("draft.md", draft)

            story = draft
            notify(85, "review", "Revisando el borrador completo")
            try:
                review = call_agent(
                    "story_critic",
                    lambda: StoryCriticAgent(self.provider).run(request, plan, draft),
                )
                repository.save_json("review.json", review)
                repository.complete_stage("review")
                notify(92, "editing", "Aplicando una edición final")
                story = call_agent(
                    "story_editor",
                    lambda: StoryEditorAgent(self.provider).run(request, plan, draft, review),
                ).strip()
                repository.complete_stage("editing")
            except Exception as exc:
                warning = (
                    "La revisión o edición final no pudo completarse; se entregó el borrador "
                    f"por capítulos ({type(exc).__name__})."
                )
                repository.add_warning(warning)
                emit("quality_fallback", warning, stage=progress["stage"])
                story = draft

            final_chapter_bodies = _parse_chapter_bodies(story, len(plan.chapters))
            if final_chapter_bodies:
                chapter_audits = []
                for chapter, body in zip(plan.chapters, final_chapter_bodies):
                    chapter_minimum, chapter_maximum = _bounds(chapter.target_words)
                    chapter_actual = _word_count(body)
                    chapter_audits.append(ChapterLengthAudit(
                        chapter_id=chapter.id,
                        target_words=chapter.target_words,
                        minimum_words=chapter_minimum,
                        maximum_words=chapter_maximum,
                        actual_words=chapter_actual,
                        within_tolerance=chapter_minimum <= chapter_actual <= chapter_maximum,
                    ))
            minimum, maximum = _bounds(request.target_words)
            actual = _word_count(story)
            repository.save_json("length_audit.json", LengthAuditArtifact(
                chapters=chapter_audits,
                total=LengthAuditEntry(
                    target_words=request.target_words,
                    minimum_words=minimum,
                    maximum_words=maximum,
                    actual_words=actual,
                    within_tolerance=minimum <= actual <= maximum,
                ),
            ))
            notify(98, "saving", "Guardando la historia")
            repository.save_text("story.md", story)
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("story")
            save_usage()
            repository.complete()
            notify(100, "completed", "Historia terminada")
            return StoryRun(repository.run_dir)
        except Exception as exc:
            emit(
                "pipeline_failed",
                f"fallo la etapa {getattr(exc, 'stage', progress['stage'])}: "
                f"{getattr(exc, 'summary', type(exc).__name__)}",
                stage=getattr(exc, "stage", progress["stage"]),
            )
            save_usage()
            repository.fail(exc)
            raise
        finally:
            if hasattr(self.provider, "usage_callback"):
                self.provider.usage_callback = None
            if hasattr(self.provider, "wait_callback"):
                self.provider.wait_callback = None

    def run(
        self,
        request: StoryRequest | str,
        on_progress: ProgressCallback | None = None,
        on_run_created=None,
        on_event: PipelineEventCallback | None = None,
    ) -> StoryRun:
        return self.generate(
            request,
            on_progress=on_progress,
            on_run_created=on_run_created,
            on_event=on_event,
        )
