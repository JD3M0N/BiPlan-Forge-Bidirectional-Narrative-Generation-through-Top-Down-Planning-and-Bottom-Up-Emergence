"""Top-Down 3.2 production orchestration with enriched English requests."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Callable, Literal, TypeVar

from pydantic import BaseModel

from asg_evaluation import create_evaluation_template

from .agents import (
    AnalystAgent, ChapterWriterAgent, CharacterDesignerAgent, CraftCriticAgent,
    CraftRewriterAgent, CraftVariantPlannerAgent, CraftVariantSelectorAgent,
    PlannerAgent, WorldBuilderAgent,
)
from .craft import (
    audit_questions, diagnostic_from_craft, validate_craft_characters,
    validate_craft_variant, validate_craft_variants,
)
from .errors import ArtifactValidationError
from .incremental import IncrementalPlotPlanner, NodeReviewHistory
from .narrative_db import NarrativeBlueprint, NarrativeSchemaRepository
from .nekg import NarrativeEntityGraph
from .progress import ProgressCallback, ProgressUpdate
from .schemas import (
    ChapterAnchorsArtifact, CharactersArtifact, CraftAuditAnswer, CraftAuditArtifact,
    CraftRevisionAttempt, CraftRevisionHistory, CraftSelectionArtifact, CraftVariant,
    CraftVariantsArtifact, IncrementalStorylineArtifact, LengthAuditArtifact,
    LengthAuditEntry, LLMUsageArtifact, NarrativeEntityGraphArtifact,
    StoryOutlineArtifact, StoryPlanArtifact, StoryRequest, WorldArtifact,
    TaxonomyBrief,
)
from .storage import ArtifactRepository


VariantId = Literal["variant-1", "variant-2", "variant-3"]
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
class _RenderedVariant:
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
    """The only production entry point for the Top-Down 3.2 pipeline."""

    def __init__(
        self,
        provider,
        output_root: Path,
        *,
        schema_repository: NarrativeSchemaRepository | None = None,
        default_target_words: int = 1500,
        max_cpn_retries: int = 2,
        max_craft_revisions: int = 2,
        max_artifact_retries: int = 2,
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
        self,
        repository: ArtifactRepository,
        *,
        name: str,
        stage: str,
        generate: Callable[[str], TArtifact],
        validate: Callable[[TArtifact], None],
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
                    "\n\nSEMANTIC REPAIR REQUIRED:\n"
                    "Return a complete replacement, not a patch. Previous candidate:\n"
                    f"{_dump(candidate)}\nVALIDATION ERROR:\n{issue}"
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
        if len(actual) != len(set(actual)) or set(actual) != set(expected) or len(actual) != len(expected):
            raise ValueError(
                "chapter anchors must match outline chapters exactly; "
                f"expected {expected}, received {actual}"
            )

    @staticmethod
    def _validate_selection(selection: CraftSelectionArtifact, variants: CraftVariantsArtifact) -> None:
        if selection.selected_variant_id not in {variant.id for variant in variants.variants}:
            raise ValueError("selected craft variant is not present")

    @staticmethod
    def _variant(variants: CraftVariantsArtifact, variant_id: VariantId) -> CraftVariant:
        return next(variant for variant in variants.variants if variant.id == variant_id)

    @staticmethod
    def _save_variant_plan(repository: ArtifactRepository, variant: CraftVariant) -> None:
        prefix = f"craft/variants/{variant.id}"
        repository.save_json(f"{prefix}/plan.json", variant)
        repository.save_data(f"{prefix}/global.json", {
            "master_line": variant.master_line.model_dump(mode="json"),
            "subplots": [line.model_dump(mode="json") for line in variant.subplots],
        })
        for chapter in variant.chapters:
            repository.save_json(f"{prefix}/chapters/{chapter.chapter_id}.json", chapter)

    @staticmethod
    def _usage_artifact(provider, start: int) -> LLMUsageArtifact:
        records = list(getattr(provider, "usage_records", []))[start:]
        return LLMUsageArtifact(
            records=records,
            calls=len(records),
            total_tokens=sum(item.total_tokens for item in records),
            total_wait_seconds=sum(item.wait_seconds for item in records),
        )

    def generate(
        self,
        request: StoryRequest | str,
        on_progress: ProgressCallback | None = None,
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
            repository.save_data(
                "taxonomy_candidates.json",
                {"candidates": [item.model_dump(mode="json") for item in blueprint.candidates]},
            )
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
                taxonomy_brief = self.schemas.compile_brief(
                    plan.taxonomy_application, blueprint,
                )
                repository.save_json(
                    "taxonomy_application.json", plan.taxonomy_application,
                )
                repository.save_json("taxonomy_brief.json", taxonomy_brief)
            repository.complete_stage("story_plan")

            world = WorldBuilderAgent(self.provider).run(request, plan, taxonomy_brief)
            repository.save_json("world.json", world)
            repository.complete_stage("world")

            character_agent = CharacterDesignerAgent(self.provider)
            characters = self._validated_artifact(
                repository, name="characters", stage="characters",
                generate=lambda feedback: character_agent.run(
                    request, plan, world, blueprint, feedback,
                    taxonomy_brief=taxonomy_brief,
                ),
                validate=validate_craft_characters,
            )
            repository.save_json("characters.json", characters)
            repository.complete_stage("characters")

            planner = IncrementalPlotPlanner(self.provider, max_retries=self.max_cpn_retries)
            outline = self._validated_artifact(
                repository, name="outline", stage="outline",
                generate=lambda feedback: planner.outline(
                    request, plan, blueprint, feedback, taxonomy_brief,
                ),
                validate=lambda value: self._validate_outline(value, request),
            )
            repository.save_json("outline.json", outline)
            repository.complete_stage("outline")

            anchors = self._validated_artifact(
                repository, name="chapter_anchors", stage="anchors",
                generate=lambda feedback: planner.anchors(outline, world, characters, feedback),
                validate=lambda value: self._validate_anchors(value, outline),
            )
            repository.save_json("chapter_anchors.json", anchors)
            repository.complete_stage("anchors")
            notify(22, "outline", "Premisa, sinopsis, capítulos y anclas terminados")

            def checkpoint(storyline, nekg, reviews) -> None:
                repository.save_json("planning_checkpoint/storyline.json", storyline)
                repository.save_json("planning_checkpoint/nekg.json", nekg)
                repository.save_json("planning_checkpoint/node_reviews.json", reviews)

            storyline, reviews = planner.plan(
                outline, anchors, blueprint, on_checkpoint=checkpoint,
                taxonomy_brief=taxonomy_brief,
                taxonomy_application=plan.taxonomy_application,
            )
            nekg = planner.nekg.artifact()
            repository.save_json("storyline.json", storyline)
            repository.save_json("nekg.json", nekg)
            repository.save_json("node_reviews.json", reviews)
            repository.complete_stage("storyline")
            notify(50, "storyline", "STORYLINE incremental validada")

            craft_agent = CraftVariantPlannerAgent(self.provider)
            variants = self._validated_artifact(
                repository, name="craft_variants", stage="craft",
                generate=lambda feedback: craft_agent.run(
                    request, plan, world, characters, outline, storyline, feedback,
                    taxonomy_brief=taxonomy_brief,
                ),
                validate=lambda value: validate_craft_variants(
                    value, outline, characters, request.target_words,
                ),
            )
            for variant in variants.variants:
                self._save_variant_plan(repository, variant)
            repository.save_json("craft/variants.json", variants)

            selector = CraftVariantSelectorAgent(self.provider)
            selection = self._validated_artifact(
                repository, name="craft_selection", stage="craft",
                generate=lambda feedback: selector.run(
                    request, characters, storyline, variants, feedback,
                    taxonomy_brief=taxonomy_brief,
                ),
                validate=lambda value: self._validate_selection(value, variants),
            )
            repository.save_json("craft/selection.json", selection)
            repository.complete_stage("craft")
            notify(58, "craft", "Tres variantes de craft creadas y una seleccionada")

            selected = self._variant(variants, selection.selected_variant_id)
            rendered = self._render_to_prefix(
                repository, request, plan, world, characters, outline, storyline,
                reviews, selected, f"craft/variants/{selected.id}", notify,
                taxonomy_brief,
            )
            self._mirror_selected(repository, rendered, outline)
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

    def _render_to_prefix(
        self,
        repository: ArtifactRepository,
        request: StoryRequest,
        plan: StoryPlanArtifact,
        world: WorldArtifact,
        characters: CharactersArtifact,
        outline: StoryOutlineArtifact,
        storyline: IncrementalStorylineArtifact,
        reviews: NodeReviewHistory,
        variant: CraftVariant,
        prefix: str,
        notify,
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> _RenderedVariant:
        usage_start = len(getattr(self.provider, "usage_records", []))
        writer = ChapterWriterAgent(self.provider)
        changes_by_node = {record.node.id: record.state_changes for record in reviews.records}
        writing_nekg = NarrativeEntityGraph()
        chapter_texts: list[str] = []
        previous_chapter = ""
        total = len(outline.chapters)
        for index, chapter in enumerate(outline.chapters, 1):
            for node in (node for node in storyline.nodes if node.chapter_id == chapter.id):
                writing_nekg.apply(node, changes_by_node.get(node.id, []))
            body = writer.run(
                request, plan, world, characters, variant, storyline,
                writing_nekg.artifact(), chapter, previous_chapter, taxonomy_brief,
            )
            text = _canonical_chapter(chapter.title, body)
            repository.save_text(f"{prefix}/chapters/chapter-{chapter.order:03d}.md", text)
            chapter_texts.append(text)
            previous_chapter = text
            notify(
                58 + index * 30 // total, "chapters",
                f"Capítulo {index} de {total} terminado", index, total,
            )
        draft = "\n\n".join(chapter_texts)
        repository.save_text(f"{prefix}/draft.md", draft)
        story, audit, revisions, warnings = self._review_draft(
            repository, request, variant, characters, outline, storyline, draft, notify, prefix,
            taxonomy_brief,
        )
        chapter_audits = []
        for chapter, text in zip(outline.chapters, chapter_texts):
            minimum, maximum = _length_bounds(chapter.target_words)
            actual = _word_count(text)
            chapter_audits.append(LengthAuditEntry(
                target_words=chapter.target_words,
                minimum_words=minimum,
                maximum_words=maximum,
                actual_words=actual,
                within_tolerance=minimum <= actual <= maximum,
            ))
        minimum, maximum = _length_bounds(request.target_words)
        actual = _word_count(story)
        length = LengthAuditArtifact(
            chapters=chapter_audits,
            total=LengthAuditEntry(
                target_words=request.target_words,
                minimum_words=minimum,
                maximum_words=maximum,
                actual_words=actual,
                within_tolerance=minimum <= actual <= maximum,
            ),
        )
        repository.save_json(f"{prefix}/craft_revision_history.json", revisions)
        repository.save_json(f"{prefix}/craft_audit.json", audit)
        repository.save_json(f"{prefix}/length_audit.json", length)
        repository.save_json(f"{prefix}/diagnostic_audit.json", diagnostic_from_craft(audit))
        repository.save_text(f"{prefix}/story.md", story)
        repository.save_json(
            f"{prefix}/llm_usage.json", self._usage_artifact(self.provider, usage_start),
        )
        if warnings:
            repository.save_data(f"{prefix}/quality_warning.json", {"warnings": warnings})
        return _RenderedVariant(story, draft, chapter_texts, audit, revisions, length, warnings)

    def _review_draft(
        self,
        repository: ArtifactRepository,
        request: StoryRequest,
        variant: CraftVariant,
        characters: CharactersArtifact,
        outline: StoryOutlineArtifact,
        storyline: IncrementalStorylineArtifact,
        draft: str,
        notify,
        prefix: str,
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> tuple[str, CraftAuditArtifact, CraftRevisionHistory, list[str]]:
        critic = CraftCriticAgent(self.provider)
        rewriter = CraftRewriterAgent(self.provider)
        versions: list[tuple[int, str, CraftAuditArtifact, bool]] = []
        history_attempts: list[CraftRevisionAttempt] = []
        warnings: list[str] = []
        minimum, maximum = _length_bounds(request.target_words)
        notify(90, "craft_critic", "Auditando el borrador")
        current_text = draft
        for attempt in range(self.max_craft_revisions + 1):
            relative_text = f"craft_revisions/attempt-{attempt}.md"
            relative_audit = f"craft_revisions/attempt-{attempt}-audit.json"
            text_file = f"{prefix}/{relative_text}"
            audit_file = f"{prefix}/{relative_audit}"
            repository.save_text(text_file, current_text)
            within_length = minimum <= _word_count(current_text) <= maximum
            critic_failed = False
            try:
                audit = critic.run(
                    request, variant, characters, outline, storyline, current_text,
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
                        **question,
                        verdict="fail",
                        evidence="La auditoría automática no estuvo disponible.",
                        issue="El criterio no pudo evaluarse.",
                        revision_instruction="Revisar este criterio manualmente.",
                    ) for question in audit_questions(
                        request, variant, characters, taxonomy_brief,
                    )],
                )
            repository.save_json(audit_file, audit)
            advisory = [answer.question_id for answer in audit.answers
                        if not answer.blocking and answer.verdict != "pass"]
            history_attempts.append(CraftRevisionAttempt(
                attempt=attempt,
                text_file=relative_text,
                audit_file=relative_audit,
                passed=audit.passed and within_length,
                failed_blocking_ids=audit.failed_blocking_ids,
                failed_advisory_ids=advisory,
            ))
            versions.append((attempt, current_text, audit, within_length))
            if critic_failed or (audit.passed and within_length) or attempt == self.max_craft_revisions:
                break
            notify(
                92 + attempt * 2, "craft_rewriter",
                f"Aplicando revisión de craft {attempt + 1} de {self.max_craft_revisions}",
            )
            actual_words = _word_count(current_text)
            length_instruction = "" if within_length else (
                f"Rewrite the complete story to contain between {minimum} and {maximum} words; "
                f"the current version has {actual_words}."
            )
            try:
                current_text = rewriter.run(
                    request, variant, characters, outline, storyline, current_text, audit,
                    length_instruction=length_instruction,
                    taxonomy_brief=taxonomy_brief,
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
                    for answer in item[2].answers),
                -item[0],
            ),
        )
        exhausted = not any(item[2].passed and item[3] for item in versions)
        if exhausted and not warnings:
            warnings.append(
                "La revisión de calidad agotó sus intentos; se entregó la mejor versión disponible."
            )
        return story, selected_audit, CraftRevisionHistory(
            selected_attempt=selected_attempt,
            exhausted=exhausted,
            attempts=history_attempts,
        ), warnings

    @staticmethod
    def _mirror_selected(
        repository: ArtifactRepository,
        rendered: _RenderedVariant,
        outline: StoryOutlineArtifact,
    ) -> None:
        repository.save_text("draft.md", rendered.draft)
        repository.save_text("story.md", rendered.story)
        repository.save_json("craft_audit.json", rendered.audit)
        repository.save_json("craft_revision_history.json", rendered.revisions)
        repository.save_json("length_audit.json", rendered.length)
        repository.save_json("diagnostic_audit.json", diagnostic_from_craft(rendered.audit))
        for chapter, text in zip(outline.chapters, rendered.chapters):
            repository.save_text(f"chapters/chapter-{chapter.order:03d}.md", text)
        if rendered.warnings:
            repository.save_data("quality_warning.json", {"warnings": rendered.warnings})
            for warning in rendered.warnings:
                repository.add_warning(warning)

    def render_variant(
        self,
        run_id: str | Path,
        variant_id: VariantId,
        on_progress: ProgressCallback | None = None,
    ) -> StoryRun:
        if variant_id not in {"variant-1", "variant-2", "variant-3"}:
            raise ValueError("variant_id must be variant-1, variant-2, or variant-3")
        run_dir = Path(run_id)
        if not run_dir.is_absolute():
            run_dir = self.output_root / run_dir
        variant_dir = run_dir / "craft" / "variants" / variant_id
        story_path = variant_dir / "story.md"
        required = [
            "request.json", "story_plan.json", "world.json", "characters.json",
            "outline.json", "storyline.json", "nekg.json", "node_reviews.json",
            "craft/selection.json", f"craft/variants/{variant_id}/plan.json",
        ]
        missing = [name for name in required if not (run_dir / name).is_file()]
        if missing:
            raise ArtifactValidationError(
                "Esta ejecución no contiene los artefactos Top-Down 3.0 necesarios para renderizar otra variante.",
                stage="render_variant",
                details={"run_dir": str(run_dir), "missing": missing},
                recommendations=["Genera una nueva historia con Top-Down 3.0 antes de usar render_variant."],
            )
        if story_path.is_file():
            return StoryRun(variant_dir)

        repository = ArtifactRepository.open_existing(run_dir)
        notify = lambda percent, stage, description, chapter=None, total=None: self._notify(
            on_progress, percent, stage, description, chapter, total,
        )
        usage_start = len(getattr(self.provider, "usage_records", []))
        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = lambda _record: repository.save_json(
                f"craft/variants/{variant_id}/llm_usage.json",
                self._usage_artifact(self.provider, usage_start),
            )
        try:
            request = StoryRequest.model_validate_json((run_dir / "request.json").read_text(encoding="utf-8"))
            plan = StoryPlanArtifact.model_validate_json((run_dir / "story_plan.json").read_text(encoding="utf-8"))
            taxonomy_brief = (
                TaxonomyBrief.model_validate_json(
                    (run_dir / "taxonomy_brief.json").read_text(encoding="utf-8")
                ) if (run_dir / "taxonomy_brief.json").is_file() else None
            )
            world = WorldArtifact.model_validate_json((run_dir / "world.json").read_text(encoding="utf-8"))
            characters = CharactersArtifact.model_validate_json((run_dir / "characters.json").read_text(encoding="utf-8"))
            outline = StoryOutlineArtifact.model_validate_json((run_dir / "outline.json").read_text(encoding="utf-8"))
            storyline = IncrementalStorylineArtifact.model_validate_json((run_dir / "storyline.json").read_text(encoding="utf-8"))
            NarrativeEntityGraphArtifact.model_validate_json(
                (run_dir / "nekg.json").read_text(encoding="utf-8")
            )
            reviews = NodeReviewHistory.model_validate_json((run_dir / "node_reviews.json").read_text(encoding="utf-8"))
            CraftSelectionArtifact.model_validate_json(
                (run_dir / "craft/selection.json").read_text(encoding="utf-8")
            )
            variant = CraftVariant.model_validate_json((variant_dir / "plan.json").read_text(encoding="utf-8"))
            validate_craft_variant(variant, outline, characters, request.target_words)
            notify(0, "render_variant", f"Redactando {variant_id} sin recalcular STORYLINE")
            self._render_to_prefix(
                repository, request, plan, world, characters, outline, storyline,
                reviews, variant, f"craft/variants/{variant_id}", notify,
                taxonomy_brief,
            )
            repository.complete()
            notify(100, "completed", f"Variante {variant_id} terminada")
            return StoryRun(variant_dir)
        except Exception:
            repository.complete()
            raise
        finally:
            if hasattr(self.provider, "usage_callback"):
                self.provider.usage_callback = None

    def run(
        self,
        request: StoryRequest | str,
        on_progress: ProgressCallback | None = None,
        on_run_created=None,
    ) -> StoryRun:
        return self.generate(request, on_progress=on_progress, on_run_created=on_run_created)

    def resume(
        self,
        run_id: str | Path,
        on_progress: ProgressCallback | None = None,
        on_run_created=None,
    ) -> StoryRun:
        run_dir = Path(run_id)
        if not run_dir.is_absolute():
            run_dir = self.output_root / run_dir
        if (run_dir / "story.md").is_file():
            return StoryRun(run_dir)
        request = StoryRequest.model_validate_json((run_dir / "request.json").read_text(encoding="utf-8"))
        return self.generate(request, on_progress=on_progress, on_run_created=on_run_created)
