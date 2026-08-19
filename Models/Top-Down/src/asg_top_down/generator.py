"""Top-Down 3.3 orchestration with modular, traceable PPP planning."""

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
    AnalystAgent, ChapterPPPPlannerAgent, ChapterWriterAgent, CharacterArcPlannerAgent,
    CharacterDesignerAgent, CraftCriticAgent, CraftRewriterAgent, GlobalPPPPlannerAgent,
    PlannerAgent, TryFailPlannerAgent, WorldBuilderAgent,
)
from .craft import (
    audit_questions, build_chapter_writing_brief, build_obligation_trace,
    build_storyline_obligations, diagnostic_from_craft, validate_chapter_ppp,
    validate_chapter_ppp_plans, validate_character_arc_plan, validate_craft_characters,
    validate_global_ppp, validate_storyline_obligations, validate_try_fail_plan,
)
from .errors import ArtifactValidationError
from .incremental import IncrementalPlotPlanner, NodeReviewHistory
from .narrative_db import NarrativeBlueprint, NarrativeSchemaRepository
from .nekg import NarrativeEntityGraph
from .progress import ProgressCallback, ProgressUpdate
from .schemas import (
    ChapterAnchorsArtifact, ChapterPPPPlan, ChapterWritingBrief, CharacterArcPlan,
    CharactersArtifact, CraftAuditAnswer, CraftAuditArtifact, CraftRevisionAttempt,
    CraftRevisionHistory, GlobalPPPPlan, IncrementalStorylineArtifact,
    LengthAuditArtifact, LengthAuditEntry, LLMUsageArtifact, StoryCraftPlan,
    StoryOutlineArtifact, StoryPlanArtifact, StoryRequest, StorylineObligationsArtifact,
    TaxonomyBrief, TryFailPlan, WorldArtifact,
)
from .storage import ArtifactRepository


TArtifact = TypeVar("TArtifact", bound=BaseModel)


class StoryRun:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)

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
    elif isinstance(value, list):
        value = [item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                 for item in value]
    return json.dumps(value, ensure_ascii=False, indent=2)


def _word_count(text: str) -> int:
    return len(text.split())


def _length_bounds(target_words: int) -> tuple[int, int]:
    return math.ceil(target_words * .90), math.floor(target_words * 1.20)


def _canonical_chapter(title: str, text: str) -> str:
    body = text.strip()
    lines = body.splitlines()
    if lines and re.match(r"^\s{0,3}#{1,6}\s+", lines[0]):
        body = "\n".join(lines[1:]).lstrip()
    return f"## {title}\n\n{body}".rstrip()


class StoryGenerator:
    """The only production entry point for the Top-Down 3.3 pipeline."""

    def __init__(
        self, provider, output_root: Path, *,
        schema_repository: NarrativeSchemaRepository | None = None,
        default_target_words: int = 1500, max_cpn_retries: int = 2,
        max_craft_revisions: int = 2, max_artifact_retries: int = 2,
    ) -> None:
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

    def _validated_artifact(
        self, repository: ArtifactRepository, *, name: str, stage: str,
        generate: Callable[[str], TArtifact], validate: Callable[[TArtifact], None],
    ) -> TArtifact:
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
                repository.save_data(
                    f"{prefix}-validation.json",
                    {"artifact": name, "stage": stage, "attempt": attempt, "issue": issue},
                )
                feedback = (
                    "\n\nSEMANTIC REPAIR REQUIRED:\nReturn a complete replacement, not a patch. "
                    f"Previous candidate:\n{_dump(candidate)}\nVALIDATION ERROR:\n{issue}"
                )
        raise ArtifactValidationError(
            f"No se pudo obtener un artefacto {name} válido después de {attempts} intentos.",
            stage=stage,
            details={"artifact": name, "attempts": attempts, "validation_errors": issues},
            recommendations=[f"Revisa artifact_attempts/{name}/ y usa un modelo más capaz."],
        )

    def _validate_plan(self, plan: StoryPlanArtifact, blueprint: NarrativeBlueprint) -> None:
        if blueprint.candidates:
            if plan.taxonomy_application is None:
                raise ValueError("new story plans require taxonomy_application")
            self.schemas.validate_application(plan.taxonomy_application, blueprint)
            return
        if plan.archetypes is None:
            raise ValueError("legacy blueprint requires archetype selection")
        allowed = {item.id for group in (
            blueprint.macroplots, blueprint.situations, blueprint.character_arcs,
        ) for item in group}
        unknown = {plan.archetypes.primary, *plan.archetypes.secondary} - allowed
        if unknown:
            raise ValueError(f"unknown retrieved archetype IDs: {', '.join(sorted(unknown))}")

    @staticmethod
    def _validate_outline(outline: StoryOutlineArtifact, request: StoryRequest) -> None:
        ids = [chapter.id for chapter in outline.chapters]
        orders = [chapter.order for chapter in outline.chapters]
        if len(ids) != len(set(ids)):
            raise ValueError("outline chapter IDs must be unique")
        if orders != list(range(1, len(orders) + 1)):
            raise ValueError("outline chapter orders must be consecutive and start at one")
        if sum(chapter.target_words for chapter in outline.chapters) != request.target_words:
            raise ValueError("chapter word budgets must equal requested target_words")

    @staticmethod
    def _validate_anchors(anchors: ChapterAnchorsArtifact, outline: StoryOutlineArtifact) -> None:
        expected = [chapter.id for chapter in outline.chapters]
        actual = [anchor.chapter_id for anchor in anchors.anchors]
        if len(actual) != len(set(actual)) or set(actual) != set(expected):
            raise ValueError(
                "chapter anchors must match outline chapters exactly; "
                f"expected {expected}, received {actual}"
            )

    @staticmethod
    def _usage_artifact(provider, start: int) -> LLMUsageArtifact:
        records = list(getattr(provider, "usage_records", []))[start:]
        return LLMUsageArtifact(
            records=records, calls=len(records),
            total_tokens=sum(item.total_tokens for item in records),
            total_wait_seconds=sum(item.wait_seconds for item in records),
        )

    def generate(
        self, request: StoryRequest | str, on_progress: ProgressCallback | None = None,
        on_run_created=None,
    ) -> StoryRun:
        progress = {"percent": 0, "stage": "analysis"}

        def notify(percent, stage, description, chapter=None, total=None) -> None:
            if stage != "rate_limit":
                progress.update(percent=percent, stage=stage)
            self._notify(on_progress, percent, stage, description, chapter, total)

        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = lambda seconds, reason: notify(
                progress["percent"], "rate_limit",
                f"Esperando cuota de Gemini: {seconds}s ({reason}; etapa {progress['stage']})",
            )
        usage_start = len(getattr(self.provider, "usage_records", []))
        notify(0, "analysis", "Analizando la solicitud")
        if isinstance(request, str):
            request = AnalystAgent(self.provider, self.default_target_words).run(request)
        repository = ArtifactRepository(self.output_root, self.provider.model_name, request.title)
        if on_run_created:
            on_run_created(repository.run_dir)

        def save_usage() -> None:
            usage = self._usage_artifact(self.provider, usage_start)
            repository.save_json("llm_usage.json", usage)
            repository.save_json("llm_usage_summary.json", usage)

        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = lambda _record: save_usage()
        try:
            repository.save_json("request.json", request)
            repository.complete_stage("analysis")
            blueprint = self.schemas.retrieve(request)
            repository.save_json("blueprint.json", blueprint)
            repository.save_json("retrieval_trace.json", blueprint.trace)
            repository.save_data("taxonomy_candidates.json", {
                "candidates": [item.model_dump(mode="json") for item in blueprint.candidates]
            })
            repository.complete_stage("retrieval")
            notify(8, "retrieval", "Esquemas narrativos recuperados")

            plan_agent = PlannerAgent(self.provider)
            plan = self._validated_artifact(
                repository, name="story_plan", stage="planning",
                generate=lambda feedback: plan_agent.run(request, blueprint, feedback),
                validate=lambda value: self._validate_plan(value, blueprint),
            )
            repository.save_json("story_plan.json", plan)
            taxonomy_brief = None
            if plan.taxonomy_application is not None:
                taxonomy_brief = self.schemas.compile_brief(plan.taxonomy_application, blueprint)
                repository.save_json("taxonomy_application.json", plan.taxonomy_application)
                repository.save_json("taxonomy_brief.json", taxonomy_brief)

            world = WorldBuilderAgent(self.provider).run(request, plan, taxonomy_brief)
            repository.save_json("world.json", world)
            character_agent = CharacterDesignerAgent(self.provider)
            characters = self._validated_artifact(
                repository, name="characters", stage="characters",
                generate=lambda feedback: character_agent.run(
                    request, plan, world, blueprint, feedback, taxonomy_brief=taxonomy_brief,
                ),
                validate=validate_craft_characters,
            )
            repository.save_json("characters.json", characters)

            frame_planner = IncrementalPlotPlanner(self.provider, max_retries=self.max_cpn_retries)
            outline = self._validated_artifact(
                repository, name="outline", stage="outline",
                generate=lambda feedback: frame_planner.outline(
                    request, plan, blueprint, feedback, taxonomy_brief,
                ),
                validate=lambda value: self._validate_outline(value, request),
            )
            repository.save_json("outline.json", outline)
            notify(22, "outline", "Premisa, sinopsis y capítulos terminados")

            global_ppp_agent = GlobalPPPPlannerAgent(self.provider)
            global_ppp = self._validated_artifact(
                repository, name="global_ppp", stage="global_ppp",
                generate=lambda feedback: global_ppp_agent.run(
                    request, plan, world, characters, outline, feedback, taxonomy_brief,
                ),
                validate=lambda value: validate_global_ppp(value, outline),
            )
            character_arcs = self._validated_artifact(
                repository, name="character_arcs", stage="character_arcs",
                generate=lambda feedback: CharacterArcPlannerAgent(self.provider).run(
                    characters, outline, global_ppp, feedback,
                ),
                validate=lambda value: validate_character_arc_plan(value, outline, characters),
            )
            try_fail = self._validated_artifact(
                repository, name="try_fail", stage="try_fail",
                generate=lambda feedback: TryFailPlannerAgent(self.provider).run(
                    request, outline, global_ppp, feedback,
                ),
                validate=lambda value: validate_try_fail_plan(value, outline, request.target_words),
            )
            repository.save_json("craft/global_ppp.json", global_ppp)
            repository.save_json("craft/character_arcs.json", character_arcs)
            repository.save_json("craft/try_fail.json", try_fail)
            obligations = build_storyline_obligations(global_ppp, character_arcs, try_fail)
            validate_storyline_obligations(obligations, outline)
            repository.save_json("storyline_obligations.json", obligations)
            repository.complete_stage("craft_planning")
            notify(36, "craft_planning", "PPP global y craft estructural terminados")

            storyline = None
            reviews = None
            nekg = None
            anchors = None
            chapter_ppps: list[ChapterPPPPlan] = []
            coverage_failures: list[dict] = []
            repair_feedback = ""
            for structural_attempt in range(2):
                planner = IncrementalPlotPlanner(self.provider, max_retries=self.max_cpn_retries)
                attempt_name = structural_attempt + 1
                anchors = self._validated_artifact(
                    repository, name=f"chapter_anchors/replan-{attempt_name}", stage="anchors",
                    generate=lambda feedback, planner=planner: planner.anchors(
                        outline, world, characters, obligations, repair_feedback + feedback,
                    ),
                    validate=lambda value: self._validate_anchors(value, outline),
                )

                def checkpoint(story, graph, history) -> None:
                    prefix = f"planning_checkpoint/replan-{attempt_name}"
                    repository.save_json(f"{prefix}/storyline.json", story)
                    repository.save_json(f"{prefix}/nekg.json", graph)
                    repository.save_json(f"{prefix}/node_reviews.json", history)

                storyline, reviews = planner.plan(
                    outline, anchors, blueprint, obligations, on_checkpoint=checkpoint,
                    taxonomy_brief=taxonomy_brief,
                    taxonomy_application=plan.taxonomy_application,
                )
                nekg = planner.nekg.artifact()
                repository.save_json(
                    f"storyline_replans/attempt-{attempt_name}/chapter_anchors.json", anchors,
                )
                repository.save_json(
                    f"storyline_replans/attempt-{attempt_name}/storyline.json", storyline,
                )
                repository.save_json(
                    f"storyline_replans/attempt-{attempt_name}/nekg.json", nekg,
                )
                repository.save_json(
                    f"storyline_replans/attempt-{attempt_name}/node_reviews.json", reviews,
                )
                try:
                    chapter_ppps = []
                    previous = None
                    local_agent = ChapterPPPPlannerAgent(self.provider)
                    for chapter in outline.chapters:
                        relevant = [item for item in obligations.obligations
                                    if item.chapter_id == chapter.id]
                        chapter_ppp = self._validated_artifact(
                            repository,
                            name=f"chapter_ppp/replan-{attempt_name}/{chapter.id}",
                            stage="chapter_ppp",
                            generate=lambda feedback, chapter=chapter, previous=previous: local_agent.run(
                                global_ppp, chapter, storyline, relevant, previous, feedback,
                            ),
                            validate=lambda value, chapter=chapter: validate_chapter_ppp(
                                value, chapter, storyline, global_ppp,
                            ),
                        )
                        chapter_ppps.append(chapter_ppp)
                        previous = chapter_ppp
                    validate_chapter_ppp_plans(chapter_ppps, outline, storyline, global_ppp)
                    break
                except (ArtifactValidationError, ValueError) as exc:
                    details = getattr(exc, "details", {})
                    failure = {
                        "attempt": attempt_name,
                        "summary": getattr(exc, "summary", str(exc)),
                        "details": details,
                    }
                    coverage_failures.append(failure)
                    repository.save_data(
                        f"storyline_replans/attempt-{attempt_name}/coverage_failure.json", failure,
                    )
                    if structural_attempt == 1:
                        raise ArtifactValidationError(
                            "La cobertura PPP siguió incompleta después de una replanificación estructural.",
                            stage="chapter_ppp",
                            details={"structural_attempts": 2, "failures": coverage_failures},
                            recommendations=[
                                "Revisa storyline_replans y los intentos de chapter_ppp."
                            ],
                        ) from exc
                    repair_feedback = (
                        "\n\nSTRUCTURAL REPLAN REQUIRED:\nThe prior STORYLINE could not ground all "
                        f"narrative obligations. Repair the anchors while preserving the outline.\n{_dump(failure)}"
                    )
            assert storyline is not None and reviews is not None and nekg is not None and anchors is not None
            repository.save_json("chapter_anchors.json", anchors)
            repository.save_json("storyline.json", storyline)
            repository.save_json("nekg.json", nekg)
            repository.save_json("node_reviews.json", reviews)
            repository.complete_stage("storyline")
            notify(58, "storyline", "STORYLINE y cobertura PPP validadas")

            briefs: list[ChapterWritingBrief] = []
            for chapter_ppp in chapter_ppps:
                brief = build_chapter_writing_brief(
                    global_ppp, chapter_ppp, character_arcs, try_fail,
                )
                briefs.append(brief)
                repository.save_json(
                    f"craft/chapters/{chapter_ppp.chapter_id}.ppp.json", chapter_ppp,
                )
                repository.save_json(
                    f"craft/chapters/{chapter_ppp.chapter_id}.brief.json", brief,
                )
            trace = build_obligation_trace(chapter_ppps)
            repository.save_json("storyline_obligation_trace.json", trace)
            craft = StoryCraftPlan(
                global_ppp=global_ppp, character_arcs=character_arcs,
                try_fail=try_fail, chapters=chapter_ppps,
            )
            rendered = self._render_story(
                repository, request, plan, world, characters, outline, storyline,
                reviews, craft, briefs, notify, taxonomy_brief,
            )
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("quality_review")
            repository.complete_stage("story")
            save_usage()
            repository.complete()
            notify(100, "completed", "Historia terminada")
            return StoryRun(repository.run_dir)
        except Exception as exc:
            save_usage()
            repository.fail(exc)
            raise
        finally:
            if hasattr(self.provider, "usage_callback"):
                self.provider.usage_callback = None
            if hasattr(self.provider, "wait_callback"):
                self.provider.wait_callback = None

    def _render_story(
        self, repository: ArtifactRepository, request: StoryRequest,
        plan: StoryPlanArtifact, world: WorldArtifact, characters: CharactersArtifact,
        outline: StoryOutlineArtifact, storyline: IncrementalStorylineArtifact,
        reviews: NodeReviewHistory, craft: StoryCraftPlan,
        briefs: list[ChapterWritingBrief], notify,
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> _RenderedStory:
        writer = ChapterWriterAgent(self.provider)
        changes_by_node = {record.node.id: record.state_changes for record in reviews.records}
        writing_nekg = NarrativeEntityGraph()
        chapter_texts: list[str] = []
        previous_chapter = ""
        total = len(outline.chapters)
        for index, (chapter, brief) in enumerate(zip(outline.chapters, briefs), 1):
            for node in (node for node in storyline.nodes if node.chapter_id == chapter.id):
                writing_nekg.apply(node, changes_by_node.get(node.id, []))
            body = writer.run(
                request, plan, world, characters, brief, storyline,
                writing_nekg.artifact(), chapter, previous_chapter, taxonomy_brief,
            )
            text = _canonical_chapter(chapter.title, body)
            repository.save_text(f"chapters/chapter-{chapter.order:03d}.md", text)
            chapter_texts.append(text)
            previous_chapter = text
            notify(58 + index * 30 // total, "chapters",
                   f"Capítulo {index} de {total} terminado", index, total)
        draft = "\n\n".join(chapter_texts)
        repository.save_text("draft.md", draft)
        story, audit, revisions, warnings = self._review_draft(
            repository, request, craft, characters, outline, storyline, draft,
            notify, taxonomy_brief,
        )
        chapter_audits = []
        for chapter, text in zip(outline.chapters, chapter_texts):
            minimum, maximum = _length_bounds(chapter.target_words)
            actual = _word_count(text)
            chapter_audits.append(LengthAuditEntry(
                target_words=chapter.target_words, minimum_words=minimum,
                maximum_words=maximum, actual_words=actual,
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
        repository.save_json("diagnostic_audit.json", diagnostic_from_craft(audit))
        repository.save_text("story.md", story)
        if warnings:
            repository.save_data("quality_warning.json", {"warnings": warnings})
            for warning in warnings:
                repository.add_warning(warning)
        return _RenderedStory(story, draft, chapter_texts, audit, revisions, length, warnings)

    def _review_draft(
        self, repository: ArtifactRepository, request: StoryRequest, craft: StoryCraftPlan,
        characters: CharactersArtifact, outline: StoryOutlineArtifact,
        storyline: IncrementalStorylineArtifact, draft: str, notify,
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> tuple[str, CraftAuditArtifact, CraftRevisionHistory, list[str]]:
        critic = CraftCriticAgent(self.provider)
        rewriter = CraftRewriterAgent(self.provider)
        versions: list[tuple[int, str, CraftAuditArtifact, bool]] = []
        attempts: list[CraftRevisionAttempt] = []
        warnings: list[str] = []
        minimum, maximum = _length_bounds(request.target_words)
        notify(90, "craft_critic", "Auditando el borrador")
        current_text = draft
        for attempt in range(self.max_craft_revisions + 1):
            text_file = f"craft_revisions/attempt-{attempt}.md"
            audit_file = f"craft_revisions/attempt-{attempt}-audit.json"
            repository.save_text(text_file, current_text)
            within_length = minimum <= _word_count(current_text) <= maximum
            critic_failed = False
            try:
                audit = critic.run(
                    request, craft, characters, outline, storyline, current_text,
                    taxonomy_brief,
                )
            except Exception as exc:
                critic_failed = True
                warning = (
                    "La auditoría de craft no pudo completarse; se conservó el mejor "
                    f"borrador disponible ({type(exc).__name__})."
                )
                warnings.append(warning)
                audit = CraftAuditArtifact(
                    summary=warning,
                    answers=[CraftAuditAnswer(
                        **question, verdict="fail",
                        evidence="La auditoría automática no estuvo disponible.",
                        issue="El criterio no pudo evaluarse.",
                        revision_instruction="Revisar este criterio manualmente.",
                    ) for question in audit_questions(
                        request, craft, characters, taxonomy_brief,
                    )],
                )
            repository.save_json(audit_file, audit)
            advisory = [answer.question_id for answer in audit.answers
                        if not answer.blocking and answer.verdict != "pass"]
            attempts.append(CraftRevisionAttempt(
                attempt=attempt, text_file=text_file, audit_file=audit_file,
                passed=audit.passed and within_length,
                failed_blocking_ids=audit.failed_blocking_ids,
                failed_advisory_ids=advisory,
            ))
            versions.append((attempt, current_text, audit, within_length))
            if critic_failed or (audit.passed and within_length) or attempt == self.max_craft_revisions:
                break
            notify(92 + attempt * 2, "craft_rewriter",
                   f"Aplicando revisión de craft {attempt + 1} de {self.max_craft_revisions}")
            actual = _word_count(current_text)
            length_instruction = "" if within_length else (
                f"Rewrite the complete story to contain between {minimum} and {maximum} words; "
                f"the current version has {actual}."
            )
            try:
                current_text = rewriter.run(
                    request, craft, characters, outline, storyline, current_text, audit,
                    length_instruction=length_instruction, taxonomy_brief=taxonomy_brief,
                )
            except Exception as exc:
                warnings.append(
                    "La reescritura de craft falló; se conservó la mejor versión "
                    f"auditada ({type(exc).__name__})."
                )
                break

        def length_distance(item) -> int:
            actual = _word_count(item[1])
            if minimum <= actual <= maximum:
                return 0
            return min(abs(actual - minimum), abs(actual - maximum))

        selected_attempt, story, selected_audit, _ = min(
            versions,
            key=lambda item: (
                len(item[2].failed_blocking_ids), length_distance(item),
                sum(not answer.blocking and answer.verdict != "pass"
                    for answer in item[2].answers), -item[0],
            ),
        )
        exhausted = not any(item[2].passed and item[3] for item in versions)
        if exhausted and not warnings:
            warnings.append(
                "La revisión de calidad agotó sus intentos; se entregó la mejor versión disponible."
            )
        return story, selected_audit, CraftRevisionHistory(
            selected_attempt=selected_attempt, exhausted=exhausted, attempts=attempts,
        ), warnings

    def run(
        self, request: StoryRequest | str, on_progress: ProgressCallback | None = None,
        on_run_created=None,
    ) -> StoryRun:
        return self.generate(request, on_progress=on_progress, on_run_created=on_run_created)

    def resume(
        self, run_id: str | Path, on_progress: ProgressCallback | None = None,
        on_run_created=None,
    ) -> StoryRun:
        run_dir = Path(run_id)
        if not run_dir.is_absolute():
            run_dir = self.output_root / run_dir
        if (run_dir / "story.md").is_file():
            return StoryRun(run_dir)
        request = StoryRequest.model_validate_json(
            (run_dir / "request.json").read_text(encoding="utf-8")
        )
        return self.generate(request, on_progress=on_progress, on_run_created=on_run_created)
