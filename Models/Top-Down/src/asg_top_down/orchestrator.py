"""Explicit orchestration for the STORYTELLER-style Top-Down pipeline."""

from pathlib import Path
import math

from asg_evaluation import create_evaluation_template

from .agents import (
    AnalystAgent, ChapterComplianceAgent, CharacterDesignerAgent, CriticAgent,
    DirectorAgent, DramaAgent, EditorAgent, PlannerAgent, SceneWriterAgent,
    WorldBuilderAgent,
)
from .graph import StorylineGraphProcessor, StorylineValidationError, render_mermaid
from .errors import (
    ASGError, ChapterComplianceError, FinalLengthError,
    FreytagValidationError, QueueRecoveryError, StorylinePlanningError,
)
from .nekg import NarrativeEntityGraph
from .provider import LanguageModelProvider
from .progress import ProgressCallback, ProgressUpdate
from .schemas import (
    ChapterComplianceAttempt, ChapterComplianceHistory, NodeReview,
    CharactersArtifact, DirectedStoryArtifact, FreytagReviewArtifact, LLMUsageArtifact,
    NodeReviewsArtifact, ReplanningAttempt, ReplanningHistoryArtifact,
    ReviewArtifact, StoryPlanArtifact, StoryRequest, StorylineArtifact, WorldArtifact,
)
from .storage import ArtifactRepository
from .taxonomies import TaxonomyRepository


def _chapter_filename(order: int) -> str:
    return f"scenes/chapter-{order:03d}.md"


def _continuity_context(text: str, limit: int = 6000) -> str:
    return text[-limit:]


def _word_count(text: str) -> int:
    return len(text.split())


def _length_bounds(target_words: int) -> tuple[int, int]:
    """Return nearest-integer bounds for the accepted -10%/+20% range."""
    return math.floor(target_words * .90 + .5), math.floor(target_words * 1.20 + .5)


def _load_checkpoint(schema, path: Path):
    if not path.is_file():
        return None
    try:
        return schema.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class StoryOrchestrator:
    def __init__(self, provider: LanguageModelProvider, output_root: Path,
                 taxonomy_root: Path | None = None) -> None:
        self.provider = provider
        self.output_root = output_root
        self.taxonomies = TaxonomyRepository(taxonomy_root, provider=provider)
        self.analyst = AnalystAgent(provider)
        self.planner = PlannerAgent(provider, self.taxonomies)
        self.world_builder = WorldBuilderAgent(provider)
        self.character_designer = CharacterDesignerAgent(provider, self.taxonomies)
        self.director = DirectorAgent(provider)
        self.graph_processor = StorylineGraphProcessor()
        self.drama = DramaAgent(provider)
        self.chapter_writer = SceneWriterAgent(provider)
        self.compliance = ChapterComplianceAgent(provider)
        self.critic = CriticAgent(provider)
        self.editor = EditorAgent(provider)

    def _build_storyline(self, request, plan, world, characters, archetypes, repository):
        history = ReplanningHistoryArtifact()
        diagnostics: list[str] = []
        for attempt in range(1, 6):
            candidate = self.director.run(
                request, plan, world, characters, archetypes,
                diagnostics=diagnostics, attempt=attempt,
            )
            repository.save_json(f"replanning/attempt-{attempt}.json", candidate)
            try:
                graph = self.graph_processor.process(candidate)
            except StorylineValidationError as exc:
                diagnostics = exc.diagnostics
                for chapter in candidate.chapters:
                    history.attempts.append(ReplanningAttempt(
                        chapter_id=chapter.id, attempt=attempt, diagnostics=diagnostics,
                    ))
                repository.save_json("replanning_history.json", history)
                continue

            drama_review = self.drama.run(graph)
            if drama_review.passed:
                repository.save_json("replanning_history.json", history)
                return graph, drama_review
            diagnostics = ["Freytag: " + issue for issue in drama_review.issues]
            if not diagnostics:
                diagnostics = ["Freytag review failed without explicit issues"]
            for chapter in graph.chapters:
                history.attempts.append(ReplanningAttempt(
                    chapter_id=chapter.id, attempt=attempt, diagnostics=diagnostics,
                ))
            repository.save_json("replanning_history.json", history)
        raise StorylinePlanningError(
            "No se obtuvo un grafo CBN-CPN-CEN válido después de cinco replanificaciones.",
            details={"attempts": 5, "diagnostics": diagnostics},
            recommendations=["Reformula el conflicto o reduce las restricciones narrativas."],
        )

    def run(
        self, prompt: str, on_progress: ProgressCallback | None = None,
        on_run_created=None,
        _resume_dir: Path | None = None,
    ) -> Path:
        last_percent = -1
        last_stage = "analyst"

        def progress(
            percent: int,
            stage: str,
            description: str,
            chapter: int | None = None,
            total_chapters: int | None = None,
        ) -> None:
            nonlocal last_percent, last_stage
            if on_progress is None or percent < last_percent:
                return
            last_percent = percent
            if stage != "rate_limit":
                last_stage = stage
            on_progress(ProgressUpdate(
                percent=percent,
                stage=stage,
                description=description,
                chapter=chapter,
                total_chapters=total_chapters,
            ))

        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = lambda seconds, reason: progress(
                max(0, last_percent), "rate_limit",
                f"Esperando cuota de Gemini: {seconds}s ({reason}; etapa {last_stage})",
            )
        progress(0, "analyst", "Analizando la solicitud")
        try:
            request = (
                StoryRequest.model_validate_json((_resume_dir / "request.json").read_text(encoding="utf-8"))
                if _resume_dir and (_resume_dir / "request.json").is_file()
                else self.analyst.run(prompt)
            )
        except Exception as exc:
            failed_repository = ArtifactRepository(
                self.output_root, self.provider.model_name, "generacion-fallida"
            )
            failed_repository.fail(exc)
            raise
        repository = (
            ArtifactRepository.open_existing(_resume_dir)
            if _resume_dir else ArtifactRepository(self.output_root, self.provider.model_name, request.title)
        )
        if on_run_created:
            on_run_created(repository.run_dir)
        usage_path = repository.run_dir / "llm_usage.json"
        prior_usage = (
            LLMUsageArtifact.model_validate_json(usage_path.read_text(encoding="utf-8")).records
            if _resume_dir and usage_path.is_file() else []
        )
        usage_start = len(getattr(self.provider, "usage_records", []))

        def save_usage() -> None:
            current = list(getattr(self.provider, "usage_records", []))[usage_start:]
            records = [*prior_usage, *current]
            artifact = LLMUsageArtifact(
                records=records, calls=len(records),
                total_tokens=sum(x.total_tokens for x in records),
                total_wait_seconds=sum(x.wait_seconds for x in records),
            )
            repository.save_json("llm_usage.json", artifact)
            repository.save_json("llm_usage_summary.json", artifact)
        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = lambda _record: save_usage()
        try:
            repository.save_json("request.json", request)
            repository.complete_stage("analyst")
            progress(10, "planner", "Planificando la historia")
            plan = _load_checkpoint(StoryPlanArtifact, repository.run_dir / "story_plan.json")
            if plan is None:
                plan = self.planner.run(request)
                repository.save_json("archetypes.json", plan.archetypes)
                repository.save_json("story_plan.json", plan)
                repository.complete_stage("planner")
            progress(20, "world", "Construyendo el mundo")
            world = _load_checkpoint(WorldArtifact, repository.run_dir / "world.json")
            if world is None:
                world = self.world_builder.run(request, plan)
                repository.save_json("world.json", world)
                repository.complete_stage("world")
            progress(30, "characters", "Diseñando los personajes")
            characters = _load_checkpoint(CharactersArtifact, repository.run_dir / "characters.json")
            if characters is None:
                characters = self.character_designer.run(request, plan, world)
                repository.save_json("characters.json", characters)
                repository.complete_stage("characters")

            archetype_ids = [plan.archetypes.primary, *plan.archetypes.secondary]
            archetypes = self.taxonomies.get_archetypes(archetype_ids)
            progress(40, "director", "Trazando el grafo narrativo")
            graph = _load_checkpoint(StorylineArtifact, repository.run_dir / "storyline.json")
            plan_drama = _load_checkpoint(FreytagReviewArtifact, repository.run_dir / "freytag_plan_review.json")
            if graph is not None and plan_drama is not None:
                try:
                    self.graph_processor.process(DirectedStoryArtifact(
                        chapters=graph.chapters, nodes=graph.nodes,
                        candidate_edges=graph.candidate_edges,
                    ))
                except StorylineValidationError:
                    graph = None
            if graph is None or plan_drama is None:
                graph, plan_drama = self._build_storyline(
                    request, plan, world, characters, archetypes, repository,
                )
                repository.complete_stage("director")
                repository.save_json("storyline.json", graph)
                repository.save_json("narrative_graph.json", graph)
                repository.save_text("narrative_graph.md", render_mermaid(graph))
                repository.save_json("freytag_plan_review.json", plan_drama)

            nekg = NarrativeEntityGraph()
            for node_id in graph.topological_order:
                nekg.add_node(next(node for node in graph.nodes if node.id == node_id))
            repository.save_json("nekg.json", nekg.artifact())
            repository.save_json("node_reviews.json", NodeReviewsArtifact(reviews=[
                NodeReview(node_id=node.id, accepted=True, explanation="Accepted into validated DAG")
                for node in graph.nodes
            ]))
            repository.complete_stage("graph")

            chapter_texts: list[str] = []
            compliance_path = repository.run_dir / "chapter_compliance.json"
            compliance_history = _load_checkpoint(ChapterComplianceHistory, compliance_path) or ChapterComplianceHistory()
            total_chapters = len(graph.chapters)
            for chapter in graph.chapters:
                chapter_number = len(chapter_texts) + 1
                chapter_start = 50 + (chapter_number - 1) * 30 // total_chapters
                progress(
                    chapter_start,
                    "scenes",
                    f"Escribiendo capítulo {chapter_number} de {total_chapters}",
                    chapter_number,
                    total_chapters,
                )
                prior = _continuity_context("\n\n".join(chapter_texts))
                existing_chapter = repository.run_dir / _chapter_filename(chapter.order)
                approved = any(
                    item.chapter_id == chapter.id and item.passed
                    for item in compliance_history.attempts
                )
                if existing_chapter.is_file() and approved:
                    chapter_texts.append(existing_chapter.read_text(encoding="utf-8").strip())
                    continue
                revision = ""
                text = ""
                for write_attempt in range(3):
                    text = self.chapter_writer.run(
                        request, plan, world, characters, graph, chapter, prior, revision,
                    )
                    audit = self.compliance.run(chapter, graph, text)
                    actual = _word_count(text)
                    chapter_nodes = [x for x in graph.nodes if x.chapter_id == chapter.id]
                    expected_nodes = [x.id for x in chapter_nodes]
                    expected_goals = [
                        f"{node.id}:{goal.taxonomy_beat}"
                        for node in chapter_nodes for goal in node.goals
                    ]
                    covered_nodes = sorted(set(audit.covered_node_ids) & set(expected_nodes))
                    covered_goals = sorted(set(audit.covered_goals) & set(expected_goals))
                    missing_nodes = sorted(set(expected_nodes) - set(covered_nodes))
                    missing_goals = sorted(set(expected_goals) - set(covered_goals))
                    attempt_record = ChapterComplianceAttempt(
                        chapter_id=chapter.id, chapter_title=chapter.title,
                        attempt=write_attempt + 1, target_words=chapter.target_words,
                        actual_words=actual, word_difference=actual - chapter.target_words,
                        expected_node_ids=expected_nodes, covered_node_ids=covered_nodes,
                        missing_node_ids=missing_nodes, expected_goals=expected_goals,
                        covered_goals=covered_goals, missing_goals=missing_goals,
                        passed=audit.passed and not missing_nodes and not missing_goals,
                        issues=audit.issues, revision_instructions=audit.revision_instructions,
                    )
                    compliance_history.attempts.append(attempt_record)
                    repository.save_text(
                        f"scenes/attempts/{chapter.id}-attempt-{write_attempt + 1}.md", text,
                    )
                    repository.save_json(
                        f"scenes/attempts/{chapter.id}-attempt-{write_attempt + 1}.json",
                        attempt_record,
                    )
                    repository.save_json("chapter_compliance.json", compliance_history)
                    if attempt_record.passed:
                        break
                    revision = "; ".join([
                        *audit.issues, *audit.revision_instructions,
                        f"Nodos ausentes: {', '.join(missing_nodes) or 'ninguno'}.",
                        f"Goals pendientes: {', '.join(missing_goals) or 'ninguno'}.",
                    ])
                else:
                    last = compliance_history.attempts[-1]
                    raise ChapterComplianceError(
                        f"No se pudo completar el capítulo {chapter.order} «{chapter.title}».",
                        details={
                            "chapter_id": chapter.id, "chapter_order": chapter.order,
                            "attempts": 3, "actual_words": last.actual_words,
                            "target_words": last.target_words,
                            "missing_node_ids": last.missing_node_ids,
                            "missing_goals": last.missing_goals,
                            "issues": last.issues,
                        },
                        recommendations=[
                            "Revisa los nodos y goals pendientes en chapter_compliance.json."
                        ],
                    )
                repository.save_text(_chapter_filename(chapter.order), text)
                chapter_texts.append(text.strip())
            progress(80, "scenes", "Capítulos terminados")
            draft = "\n\n".join(chapter_texts)
            repository.save_text("draft.md", draft)
            repository.complete_stage("scenes")

            progress(85, "review", "Revisando el borrador")
            story_drama_path = repository.run_dir / "dramatic_revisions" / "attempt-0-freytag.json"
            story_drama = _load_checkpoint(FreytagReviewArtifact, story_drama_path)
            if story_drama is None:
                story_drama = self.drama.run(graph, draft)
                repository.save_text("dramatic_revisions/attempt-0.md", draft)
                repository.save_json("dramatic_revisions/attempt-0-freytag.json", story_drama)
            if not story_drama.passed:
                for drama_index in range(1, 3):
                    saved_draft = repository.run_dir / "dramatic_revisions" / f"attempt-{drama_index}.md"
                    saved_review = repository.run_dir / "dramatic_revisions" / f"attempt-{drama_index}-freytag.json"
                    checkpoint_review = _load_checkpoint(FreytagReviewArtifact, saved_review)
                    if saved_draft.is_file() and checkpoint_review is not None:
                        draft = saved_draft.read_text(encoding="utf-8")
                        story_drama = checkpoint_review
                        if story_drama.passed:
                            break
                        continue
                    correction = "; ".join(story_drama.revision_instructions or story_drama.issues)
                    # Correct the complete prose while preserving the validated DAG.
                    provisional_review = self.critic.run(request, plan, graph, draft)
                    provisional_review.revision_instructions.extend([correction])
                    draft = self.editor.run(request, plan, graph, draft, provisional_review)
                    repository.save_text(f"dramatic_revisions/attempt-{drama_index}.md", draft)
                    story_drama = self.drama.run(graph, draft)
                    repository.save_json(
                        f"dramatic_revisions/attempt-{drama_index}-freytag.json", story_drama,
                    )
                    if story_drama.passed:
                        break
            if not story_drama.passed:
                raise FreytagValidationError(
                    "La historia no cumplió la pirámide de Freytag después de dos correcciones.",
                    details={"issues": story_drama.issues, "attempts": 3},
                    recommendations=story_drama.revision_instructions,
                )

            review_path = repository.run_dir / "review.json"
            if review_path.is_file():
                review = ReviewArtifact.model_validate_json(review_path.read_text(encoding="utf-8"))
            else:
                review = self.critic.run(request, plan, graph, draft)
                repository.save_json("review.json", review)
                repository.complete_stage("review")
            correction = ""
            story = draft
            minimum, maximum = _length_bounds(request.target_words)
            progress(90, "editing", "Editando la versión final")
            editing_dir = repository.run_dir / "editing"
            existing_attempts = sorted(editing_dir.glob("attempt-*.md")) if editing_dir.is_dir() else []
            editing_complete = False
            final_drama = story_drama
            total = _word_count(story)
            if existing_attempts:
                story = existing_attempts[-1].read_text(encoding="utf-8")
                total = _word_count(story)
                saved_drama = editing_dir / f"attempt-{len(existing_attempts)}-freytag.json"
                final_drama = (
                    FreytagReviewArtifact.model_validate_json(saved_drama.read_text(encoding="utf-8"))
                    if saved_drama.is_file() else self.drama.run(graph, story)
                )
                editing_complete = minimum <= total <= maximum and final_drama.passed
            for edit_index in range(len(existing_attempts), 3):
                if editing_complete:
                    break
                story = self.editor.run(request, plan, graph, story, review, correction)
                total = _word_count(story)
                final_drama = self.drama.run(graph, story)
                repository.save_text(f"editing/attempt-{edit_index + 1}.md", story)
                repository.save_json(f"editing/attempt-{edit_index + 1}-freytag.json", final_drama)
                length_ok = minimum <= total <= maximum
                if length_ok and final_drama.passed:
                    editing_complete = True
                    break
                correction = "; ".join([
                    *final_drama.issues, *final_drama.revision_instructions,
                    f"Conteo {total}; ajustar al rango permitido {minimum}-{maximum} palabras.",
                ])
            if not editing_complete:
                if not final_drama.passed:
                    raise FreytagValidationError(
                        "La versión final no conservó la pirámide de Freytag después de dos correcciones.",
                        details={"issues": final_drama.issues, "attempts": 3},
                        recommendations=final_drama.revision_instructions,
                    )
                raise FinalLengthError(
                    f"La historia terminó con {total} palabras; se permiten entre {minimum} y {maximum}.",
                    details={
                        "actual_words": total, "target_words": request.target_words,
                        "minimum_words": minimum, "maximum_words": maximum,
                        "attempts": 3,
                    },
                    recommendations=["Aumenta el margen solicitado o simplifica la trama."],
                )
            repository.save_json("freytag_story_review.json", final_drama)
            progress(98, "saving", "Guardando la historia")
            repository.save_text("story.md", story)
            save_usage()
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("story")
            repository.complete()
            progress(100, "completed", "Historia terminada")
            return repository.run_dir
        except Exception as exc:
            save_usage()
            repository.fail(exc)
            raise
        finally:
            if hasattr(self.provider, "usage_callback"):
                self.provider.usage_callback = None

    def resume(self, run_dir: Path, on_progress: ProgressCallback | None = None,
               on_run_created=None) -> Path:
        """Recover a queued run; completed runs are delivered without regeneration."""
        from .schemas import StoryRequest

        run_dir = Path(run_dir)
        if (run_dir / "story.md").is_file():
            return run_dir
        request_path = run_dir / "request.json"
        if not request_path.is_file():
            raise QueueRecoveryError(
                "No existe un checkpoint de solicitud válido para reanudar la historia.",
                details={"run_dir": str(run_dir)},
                recommendations=["Envía nuevamente la solicitud."],
            )
        request = StoryRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
        return self.run(
            request.original_prompt, on_progress, on_run_created,
            _resume_dir=run_dir,
        )
