"""Top-Down 4.1 orchestration with a frozen factual/craft boundary."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Callable, TypeVar

from pydantic import BaseModel

from asg_evaluation import create_evaluation_template

from .agents import (
    AnalystAgent, ChapterRewriterAgent, ChapterWriterAgent, CharacterArcPlannerAgent,
    CharacterDesignerAgent, CraftComposerAgent, CraftCriticAgent, PlannerAgent,
    PromiseLedgerPlannerAgent, TryFailPlannerAgent, WorldBuilderAgent,
)
from .craft import (
    audit_questions, build_chapter_writing_brief, validate_character_arc_plan,
    validate_craft_alignment, validate_craft_characters, validate_promise_ledger,
    validate_try_fail_plan,
)
from .errors import ArtifactValidationError
from .incremental import IncrementalPlotPlanner, NodeReviewHistory, chapter_word_budgets
from .narrative_db import NarrativeBlueprint, NarrativeSchemaRepository
from .nekg import NarrativeEntityGraph
from .progress import (
    PipelineEvent, PipelineEventCallback, ProgressCallback, ProgressUpdate,
)
from .schemas import (
    ChapterAnchorsArtifact, CharactersArtifact,
    CraftAuditAnswer, CraftAuditArtifact, CraftRevisionAttempt, CraftRevisionHistory,
    IncrementalStorylineArtifact, LengthAuditArtifact, LengthAuditEntry,
    LLMUsageArtifact, StoryCraftPlan, StoryOutlineArtifact, StoryPlanArtifact,
    StoryRequest, TaxonomyBrief, WorldArtifact,
)
from .storage import ArtifactRepository


TArtifact = TypeVar("TArtifact", bound=BaseModel)


class StoryRun:
    """Stable handle for completed 4.x and historical completed 3.x runs."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        metadata_path = self.run_dir / "metadata.json"
        if self.run_dir.exists() and metadata_path.is_file() and not self.story_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metadata = {}
            version = str(metadata.get("pipeline_version", "unknown"))
            raise ArtifactValidationError(
                f"La ejecución Top-Down {version} está incompleta y no puede abrirse como StoryRun 4.1.",
                stage="compatibility", details={"run_id": str(self.run_dir), "version": version},
                recommendations=["Usa un run terminado con story.md o inicia una ejecución 4.1 nueva."],
            )

    @property
    def story_path(self) -> Path:
        return self.run_dir / "story.md"

    def __fspath__(self) -> str:
        return str(self.run_dir)


@dataclass
class _RenderedStory:
    story: str
    draft: str
    chapters: list[str]
    audit: CraftAuditArtifact
    revisions: CraftRevisionHistory
    length: LengthAuditArtifact
    warnings: list[str]


def _dump(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, indent=2)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def _length_bounds(target_words: int) -> tuple[int, int]:
    return math.ceil(target_words * .90), math.floor(target_words * 1.20)


def _canonical_chapter(title: str, text: str) -> str:
    body = text.strip()
    lines = body.splitlines()
    if lines and re.match(r"^\s{0,3}#{1,6}\s+", lines[0]):
        body = "\n".join(lines[1:]).lstrip()
    return f"## {title}\n\n{body}".rstrip()


def _parse_story(story: str, outline: StoryOutlineArtifact) -> list[str]:
    matches = list(re.finditer(r"(?m)^##\s+.+$", story))
    if len(matches) != len(outline.chapters):
        raise ValueError("selected story does not contain the canonical chapter count")
    return [
        story[match.start():(matches[index + 1].start() if index + 1 < len(matches) else len(story))].strip()
        for index, match in enumerate(matches)
    ]


class StoryGenerator:
    """Public Top-Down 4.1 generator."""

    def __init__(self, provider, output_root: Path, *,
                 schema_repository: NarrativeSchemaRepository | None = None,
                 default_target_words: int = 1500, max_cpn_retries: int = 2,
                 max_craft_revisions: int = 2, max_artifact_retries: int = 2) -> None:
        if min(max_cpn_retries, max_craft_revisions, max_artifact_retries) < 0:
            raise ValueError("retry counts cannot be negative")
        self.provider = provider
        self.output_root = Path(output_root)
        self.default_target_words = default_target_words
        self.schemas = schema_repository or NarrativeSchemaRepository(provider=provider)
        self.max_cpn_retries = max_cpn_retries
        self.max_craft_revisions = max_craft_revisions
        self.max_artifact_retries = max_artifact_retries

    def _notify(self, callback, percent, stage, description, chapter=None, total=None) -> None:
        if callback:
            callback(ProgressUpdate(percent, stage, description, chapter, total))

    def _validated_artifact(self, repository: ArtifactRepository, *, name: str, stage: str,
                            generate: Callable[[str], TArtifact],
                            validate: Callable[[TArtifact], None]) -> TArtifact:
        issues: list[str] = []
        feedback = ""
        attempts = self.max_artifact_retries + 1
        for attempt in range(1, attempts + 1):
            candidate = generate(feedback)
            try:
                validate(candidate)
                return candidate
            except (AssertionError, KeyError, ValueError) as exc:
                issue = str(exc).strip() or type(exc).__name__
                issues.append(issue)
                prefix = f"artifact_attempts/{name}/attempt-{attempt:03d}"
                repository.save_json(f"{prefix}.json", candidate)
                repository.save_data(f"{prefix}-validation.json", {
                    "artifact": name, "stage": stage, "attempt": attempt, "issue": issue,
                })
                feedback = (
                    "\n\nREPAIR ONLY THIS ARTIFACT. Return a complete replacement. "
                    f"Validation error: {issue}\nPrevious value:\n{_dump(candidate)}"
                )
        raise ArtifactValidationError(
            f"No se pudo validar {name} después de {attempts} intentos.", stage=stage,
            details={"artifact": name, "validation_errors": issues},
            recommendations=[f"Revisa artifact_attempts/{name}/."],
        )

    def _validate_plan(self, plan: StoryPlanArtifact, blueprint: NarrativeBlueprint) -> None:
        self.schemas.validate_application(plan.taxonomy_application, blueprint)

    @staticmethod
    def _validate_outline(outline: StoryOutlineArtifact, request: StoryRequest) -> None:
        ids = [item.id for item in outline.chapters]
        orders = [item.order for item in outline.chapters]
        if len(ids) != len(set(ids)) or orders != list(range(1, len(orders) + 1)):
            raise ValueError("outline IDs/orders must be unique and consecutive")
        budgets = chapter_word_budgets(request.agent_spec())
        if len(outline.chapters) != len(budgets):
            raise ValueError(f"outline must contain exactly {len(budgets)} chapters")
        if [item.target_words for item in outline.chapters] != budgets:
            raise ValueError(f"chapter budgets must exactly equal {budgets}")

    @staticmethod
    def _validate_world_characters(world: WorldArtifact, characters: CharactersArtifact) -> None:
        locations = {item.id for item in world.locations}
        character_ids = {item.id for item in characters.characters}
        bad_locations = {item.initial_location_id for item in characters.characters
                         if item.initial_location_id not in locations}
        bad_owners = {item.initial_owner_character_id for item in world.objects
                      if item.initial_owner_character_id and item.initial_owner_character_id not in character_ids}
        if bad_locations or bad_owners:
            raise ValueError(f"invalid initial entity references: locations={bad_locations}, owners={bad_owners}")

    @staticmethod
    def _validate_anchors(anchors: ChapterAnchorsArtifact, outline: StoryOutlineArtifact) -> None:
        expected = {item.id for item in outline.chapters}
        actual = [item.chapter_id for item in anchors.anchors]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError("chapter anchors must match outline chapters exactly")

    @staticmethod
    def _usage_artifact(provider, start: int) -> LLMUsageArtifact:
        records = list(getattr(provider, "usage_records", []))[start:]
        return LLMUsageArtifact(
            records=records, calls=len(records),
            failed_calls=sum(item.status == "failed" for item in records),
            total_tokens=sum(item.total_tokens for item in records),
            total_wait_seconds=sum(item.wait_seconds for item in records),
        )

    @staticmethod
    def _cpn_call_count(provider) -> int:
        return sum(
            any(name in item.operation for name in ("PlotNodeProposal", "PlotNodeReview"))
            for item in getattr(provider, "usage_records", [])
        )

    def generate(self, request: StoryRequest | str,
                 on_progress: ProgressCallback | None = None,
                 on_run_created=None,
                 on_event: PipelineEventCallback | None = None) -> StoryRun:
        progress = {"percent": 0, "stage": "analysis"}

        def emit(kind: str, message: str, *, stage: str | None = None,
                 chapter_id: str | None = None, attempt: int | None = None,
                 artifact: str | None = None) -> None:
            if on_event:
                on_event(PipelineEvent(
                    kind=kind, message=message, stage=stage,
                    chapter_id=chapter_id, attempt=attempt, artifact=artifact,
                ))

        def call_agent(name: str, function: Callable[[], TArtifact | str]):
            emit("agent_called", f"se llamo al agente {name}", stage=progress["stage"])
            return function()

        def notify(percent, stage, description, chapter=None, total=None) -> None:
            if stage != "rate_limit":
                progress.update(percent=percent, stage=stage)
            self._notify(on_progress, percent, stage, description, chapter, total)

        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = lambda seconds, reason: notify(
                progress["percent"], "rate_limit", f"Esperando cuota: {seconds}s ({reason})",
            )
        usage_start = len(getattr(self.provider, "usage_records", []))
        notify(0, "analysis", "Analizando la solicitud")
        if isinstance(request, str):
            request = call_agent(
                "analyst",
                lambda: AnalystAgent(self.provider, self.default_target_words).run(request),
            )
        repository = ArtifactRepository(
            self.output_root, self.provider.model_name, request.title,
            on_artifact=lambda filename, created: emit(
                "artifact_created" if created else "artifact_updated",
                f"artefacto {filename} {'creado' if created else 'actualizado'}",
                stage=progress["stage"], artifact=filename,
            ),
        )
        if on_run_created:
            on_run_created(repository.run_dir)

        for record in list(getattr(self.provider, "usage_records", []))[usage_start:]:
            repository.append_llm_call(record)

        def save_usage() -> None:
            repository.save_json("llm_usage.json", self._usage_artifact(self.provider, usage_start))

        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = lambda record: (
                repository.append_llm_call(record), save_usage(),
            )
        try:
            try:
                chapter_word_budgets(request.agent_spec())
            except ValueError as exc:
                raise ArtifactValidationError(
                    "La extensiÃ³n solicitada no permite el nÃºmero de capÃ­tulos indicado.",
                    stage="outline", details={"issue": str(exc)},
                    recommendations=["Reduce los capÃ­tulos o aumenta la cantidad de palabras."],
                ) from exc
            repository.save_json("request.json", request)
            repository.complete_stage("analysis")
            emit("function_called", "se llamo a la funcion recuperacion taxonomica", stage="retrieval")
            blueprint = self.schemas.retrieve(request)
            repository.save_json("blueprint.json", blueprint)
            repository.save_json("retrieval_trace.json", blueprint.trace)
            repository.complete_stage("retrieval")

            plan = self._validated_artifact(
                repository, name="story_plan", stage="planning",
                generate=lambda feedback: call_agent(
                    "planner", lambda: PlannerAgent(self.provider).run(request, blueprint, feedback),
                ),
                validate=lambda value: self._validate_plan(value, blueprint),
            )
            taxonomy_brief = self.schemas.compile_brief(plan.taxonomy_application, blueprint)
            repository.save_json("story_plan.json", plan)
            repository.save_json("story_frame.json", plan.story_frame)
            repository.save_json("taxonomy_application.json", plan.taxonomy_application)
            repository.save_json("taxonomy_brief.json", taxonomy_brief)
            world = call_agent(
                "world", lambda: WorldBuilderAgent(self.provider).run(
                    request, plan, taxonomy_brief,
                ),
            )
            repository.save_json("world.json", world)
            characters = self._validated_artifact(
                repository, name="characters", stage="characters",
                generate=lambda feedback: call_agent(
                    "characters", lambda: CharacterDesignerAgent(self.provider).run(
                        request, plan, world, feedback, taxonomy_brief,
                    ),
                ),
                validate=lambda value: (
                    validate_craft_characters(value), self._validate_world_characters(world, value),
                ),
            )
            repository.save_json("characters.json", characters)
            storyline_cast = characters.storyline_cast()

            def save_storyline_attempt(record: dict) -> None:
                chapter_id = str(record.get("chapter_id", "unknown"))
                slot = int(record.get("slot", 0))
                attempt = int(record.get("attempt", 0))
                stage = str(record.get("stage", "unknown"))
                repository.save_data(
                    f"storyline_attempts/{chapter_id}/slot-{slot:02d}/"
                    f"attempt-{attempt:02d}-{stage}.json",
                    record,
                )

            factual = IncrementalPlotPlanner(
                self.provider, max_retries=self.max_cpn_retries,
                on_event=on_event, on_attempt=save_storyline_attempt,
            )
            outline = self._validated_artifact(
                repository, name="outline", stage="outline",
                generate=lambda feedback: call_agent(
                    "outline", lambda: factual.outline(
                        request.agent_spec(), plan, blueprint, feedback, taxonomy_brief,
                    ),
                ),
                validate=lambda value: self._validate_outline(value, request),
            )
            repository.save_json("outline.json", outline)
            anchors = self._validated_artifact(
                repository, name="chapter_anchors", stage="anchors",
                generate=lambda feedback: call_agent(
                    "chapter_anchors", lambda: factual.anchors(
                        outline, world, storyline_cast, plan.story_frame, feedback,
                    ),
                ),
                validate=lambda value: self._validate_anchors(value, outline),
            )
            repository.save_json("chapter_anchors.json", anchors)
            checkpoint = {"number": 0}

            def save_checkpoint(story, graph, reviews) -> None:
                checkpoint["number"] += 1
                prefix = f"checkpoints/{checkpoint['number']:05d}"
                repository.save_json(f"{prefix}/storyline.json", story)
                repository.save_json(f"{prefix}/nekg.json", graph)
                repository.save_json(f"{prefix}/node_reviews.json", reviews)

            emit("function_called", "se llamo a la funcion planificacion incremental", stage="storyline")
            storyline, reviews = factual.plan(
                outline, anchors, blueprint, world, storyline_cast, plan.story_frame,
                on_checkpoint=save_checkpoint, taxonomy_brief=taxonomy_brief,
                taxonomy_application=plan.taxonomy_application,
            )
            repository.save_json("chapter_anchors.json", anchors)
            nekg = factual.nekg.artifact()
            repository.save_json("storyline.json", storyline)
            repository.save_json("nekg.json", nekg)
            repository.save_json("node_reviews.json", reviews)
            repository.complete_stage("storyline_frozen")
            frozen_storyline = storyline.model_dump_json()
            frozen_cpn_calls = self._cpn_call_count(self.provider)
            notify(52, "storyline", "STORYLINE factual congelada")

            ledger = self._validated_artifact(
                repository, name="promise_ledger", stage="craft",
                generate=lambda feedback: call_agent(
                    "promise_ledger", lambda: PromiseLedgerPlannerAgent(self.provider).run(
                        request, plan, characters, outline, storyline, taxonomy_brief, feedback,
                    ),
                ),
                validate=lambda value: validate_promise_ledger(value, outline, request.target_words),
            )
            arcs = self._validated_artifact(
                repository, name="character_arcs", stage="craft",
                generate=lambda feedback: call_agent(
                    "character_arcs", lambda: CharacterArcPlannerAgent(self.provider).run(
                        characters, outline, storyline, ledger, feedback,
                    ),
                ),
                validate=lambda value: validate_character_arc_plan(
                    value, characters, outline, ledger,
                ),
            )
            try_fail = self._validated_artifact(
                repository, name="try_fail", stage="craft",
                generate=lambda feedback: call_agent(
                    "try_fail", lambda: TryFailPlannerAgent(self.provider).run(
                        request, outline, storyline, ledger, feedback,
                    ),
                ),
                validate=lambda value: validate_try_fail_plan(value, request, outline, ledger),
            )
            composition = self._validated_artifact(
                repository, name="craft_alignment", stage="craft",
                generate=lambda feedback: call_agent(
                    "craft_alignment", lambda: CraftComposerAgent(self.provider).run(
                        outline, storyline, ledger, arcs, try_fail, feedback,
                    ),
                ),
                validate=lambda value: validate_craft_alignment(
                    value.alignment, value.chapters, ledger, arcs, try_fail, outline, storyline,
                ),
            )
            craft = StoryCraftPlan(
                promise_ledger=ledger, character_arcs=arcs, try_fail=try_fail,
                alignment=composition.alignment, chapters=composition.chapters,
            )
            if (storyline.model_dump_json() != frozen_storyline
                    or self._cpn_call_count(self.provider) != frozen_cpn_calls):
                raise ArtifactValidationError(
                    "Craft intentó modificar o volver a consultar la STORYLINE congelada.",
                    stage="architecture",
                    details={"boundary": "storyline_frozen -> craft"},
                )
            repository.save_json("craft/promise_ledger.json", ledger)
            repository.save_json("craft/character_arcs.json", arcs)
            repository.save_json("craft/try_fail.json", try_fail)
            repository.save_json("craft/alignment.json", composition.alignment)
            repository.save_json("craft/plan.json", craft)
            for chapter in outline.chapters:
                view = next(item for item in composition.chapters if item.chapter_id == chapter.id)
                repository.save_json(f"craft/chapters/{chapter.id}.view.json", view)
            repository.complete_stage("craft")
            notify(68, "craft", "Craft alineado sin modificar STORYLINE")

            rendered = self._render_story(
                repository, request, plan, world, characters, outline, storyline,
                craft, notify, taxonomy_brief, emit,
            )
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("quality_review")
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

    def _render_story(self, repository: ArtifactRepository, request: StoryRequest,
                      plan: StoryPlanArtifact, world: WorldArtifact,
                      characters: CharactersArtifact, outline: StoryOutlineArtifact,
                      storyline: IncrementalStorylineArtifact, craft: StoryCraftPlan,
                      notify, taxonomy_brief: TaxonomyBrief | None, emit) -> _RenderedStory:
        writer = ChapterWriterAgent(self.provider)
        graph = NarrativeEntityGraph(world, characters.storyline_cast())
        bodies: list[str] = []
        previous = ""
        for index, chapter in enumerate(outline.chapters, 1):
            before = graph.snapshot()
            repository.save_json(f"chapters/state-before-{chapter.id}.json", before)
            brief = build_chapter_writing_brief(
                chapter.id, craft, characters, storyline, before,
            )
            repository.save_json(f"craft/chapters/{chapter.id}.brief.json", brief)
            emit(
                "agent_called", "se llamo al agente chapter_writer",
                stage="chapters", chapter_id=chapter.id,
            )
            body = writer.run(
                request, plan, world, brief, chapter, previous,
            )
            bodies.append(body.strip())
            previous = _canonical_chapter(chapter.title, body)
            repository.save_text(f"chapters/chapter-{chapter.order:03d}.md", previous)
            for node in storyline.nodes:
                if node.chapter_id == chapter.id:
                    graph.apply(node)
            notify(68 + index * 20 // len(outline.chapters), "chapters",
                   f"Capítulo {index} de {len(outline.chapters)} terminado", index, len(outline.chapters))
        draft = "\n\n".join(
            _canonical_chapter(chapter.title, body)
            for chapter, body in zip(outline.chapters, bodies)
        )
        repository.save_text("draft.md", draft)
        story, audit, revisions, warnings = self._review_draft(
            repository, request, craft, characters, outline, storyline, bodies,
            notify, taxonomy_brief, emit,
        )
        parsed = _parse_story(story, outline)
        chapter_audits = []
        for chapter, text in zip(outline.chapters, parsed):
            minimum, maximum = _length_bounds(chapter.target_words)
            actual = _word_count(text)
            chapter_audits.append(LengthAuditEntry(
                chapter_id=chapter.id, target_words=chapter.target_words,
                minimum_words=minimum, maximum_words=maximum, actual_words=actual,
                within_tolerance=minimum <= actual <= maximum,
            ))
        minimum, maximum = _length_bounds(request.target_words)
        actual = _word_count(story)
        length = LengthAuditArtifact(
            chapters=chapter_audits,
            total=LengthAuditEntry(
                target_words=request.target_words, minimum_words=minimum,
                maximum_words=maximum, actual_words=actual,
                within_tolerance=minimum <= actual <= maximum,
            ),
        )
        repository.save_json("craft_revision_history.json", revisions)
        repository.save_json("craft_audit.json", audit)
        repository.save_json("length_audit.json", length)
        repository.save_text("story.md", story)
        if warnings:
            repository.save_data("quality_warning.json", {"warnings": warnings})
            for warning in warnings:
                repository.add_warning(warning)
        return _RenderedStory(story, draft, parsed, audit, revisions, length, warnings)

    def _review_draft(self, repository: ArtifactRepository, request: StoryRequest,
                      craft: StoryCraftPlan, characters: CharactersArtifact,
                      outline: StoryOutlineArtifact, storyline: IncrementalStorylineArtifact,
                      initial_bodies: list[str], notify,
                      taxonomy_brief: TaxonomyBrief | None, emit):
        critic = CraftCriticAgent(self.provider)
        rewriter = ChapterRewriterAgent(self.provider)
        bodies = list(initial_bodies)
        attempts: list[CraftRevisionAttempt] = []
        versions: list[tuple[int, list[str], CraftAuditArtifact]] = []
        warnings: list[str] = []
        for attempt in range(self.max_craft_revisions + 1):
            story = "\n\n".join(
                _canonical_chapter(chapter.title, body)
                for chapter, body in zip(outline.chapters, bodies)
            )
            text_file = f"craft_revisions/attempt-{attempt}.md"
            audit_file = f"craft_revisions/attempt-{attempt}-audit.json"
            repository.save_text(text_file, story)
            try:
                emit(
                    "agent_called", "se llamo al agente craft_critic",
                    stage="quality_review", attempt=attempt + 1,
                )
                audit = critic.run(
                    request, craft, characters, outline, storyline, story, taxonomy_brief,
                )
            except Exception as exc:
                warning = f"La auditoría de craft falló ({type(exc).__name__}); requiere revisión humana."
                warnings.append(warning)
                audit = CraftAuditArtifact(summary=warning, answers=[CraftAuditAnswer(
                    **question, verdict="fail", evidence="Auditoría no disponible.",
                    issue="Criterio no evaluado.", revision_instruction="Revisar manualmente.",
                ) for question in audit_questions(request, craft, characters, taxonomy_brief)])
            repository.save_json(audit_file, audit)
            chapter_lengths = []
            for chapter, body in zip(outline.chapters, bodies):
                lower, upper = _length_bounds(chapter.target_words)
                if not lower <= _word_count(body) <= upper:
                    chapter_lengths.append(chapter.id)
            affected = set(audit.affected_chapter_ids) | set(chapter_lengths)
            if audit.failed_blocking_ids and not audit.affected_chapter_ids:
                affected.update(item.id for item in outline.chapters)
            passed = audit.passed and not chapter_lengths
            attempts.append(CraftRevisionAttempt(
                attempt=attempt, text_file=text_file, audit_file=audit_file, passed=passed,
                repaired_chapter_ids=sorted(affected) if attempt < self.max_craft_revisions else [],
                failed_blocking_ids=audit.failed_blocking_ids,
                failed_advisory_ids=[item.question_id for item in audit.answers
                                     if not item.blocking and item.verdict != "pass"],
            ))
            versions.append((attempt, list(bodies), audit))
            if passed or attempt == self.max_craft_revisions or warnings:
                break
            notify(90 + attempt * 3, "chapter_repair", "Reparando capítulos afectados")
            repair_failed = False
            for index, chapter in enumerate(outline.chapters):
                if chapter.id not in affected:
                    continue
                failed = [item for item in audit.answers
                          if item.verdict == "fail" and (
                              not item.chapter_ids or chapter.id in item.chapter_ids
                          )]
                lower, upper = _length_bounds(chapter.target_words)
                try:
                    emit(
                        "agent_called", "se llamo al agente chapter_rewriter",
                        stage="chapter_repair", chapter_id=chapter.id,
                        attempt=attempt + 1,
                    )
                    bodies[index] = rewriter.run(
                        request, chapter.id, chapter.title, bodies[index],
                        {"chapter": chapter.model_dump(mode="json"),
                         "brief": build_chapter_writing_brief(
                             chapter.id, craft, characters, storyline,
                         )},
                        failed, f"Keep the chapter between {lower} and {upper} words.",
                    )
                except Exception as exc:
                    warnings.append(
                        "La reparación selectiva falló; se conservó la mejor versión "
                        f"auditada ({type(exc).__name__})."
                    )
                    repair_failed = True
                    break
            if repair_failed:
                break

        def quality(item) -> tuple[int, int, int]:
            _, candidate_bodies, audit = item
            story = " ".join(candidate_bodies)
            low, high = _length_bounds(request.target_words)
            actual = _word_count(story)
            distance = 0 if low <= actual <= high else min(abs(actual-low), abs(actual-high))
            return len(audit.failed_blocking_ids), distance, -item[0]

        selected_attempt, selected_bodies, selected_audit = min(versions, key=quality)
        story = "\n\n".join(
            _canonical_chapter(chapter.title, body)
            for chapter, body in zip(outline.chapters, selected_bodies)
        )
        exhausted = not any(item.passed for item in attempts)
        if exhausted and not warnings:
            warnings.append("Se agotaron las reparaciones; se entregó la mejor versión auditada.")
        return story, selected_audit, CraftRevisionHistory(
            selected_attempt=selected_attempt, exhausted=exhausted, attempts=attempts,
        ), warnings

    def run(self, request: StoryRequest | str,
            on_progress: ProgressCallback | None = None, on_run_created=None,
            on_event: PipelineEventCallback | None = None) -> StoryRun:
        return self.generate(
            request, on_progress=on_progress, on_run_created=on_run_created,
            on_event=on_event,
        )
