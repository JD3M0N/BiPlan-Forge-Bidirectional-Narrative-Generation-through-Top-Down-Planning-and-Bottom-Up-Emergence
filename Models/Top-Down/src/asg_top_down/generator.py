"""Production STORYTELLER generator built around incremental accepted events."""

from __future__ import annotations

from pathlib import Path
import json
import math
import re
from typing import Callable, TypeVar

from pydantic import BaseModel

from asg_evaluation import create_evaluation_template

from .agents.analyst import AnalystAgent
from .agents.craft import CraftContractAgent, CraftCriticAgent, CraftRewriterAgent
from .craft import (
    audit_questions, diagnostic_from_craft,
    validate_craft_characters, validate_craft_contract, validate_craft_outline,
)
from .errors import ArtifactValidationError
from .incremental import IncrementalPlotPlanner
from .narrative_db import NarrativeBlueprint, NarrativeSchemaRepository
from .nekg import NarrativeEntityGraph
from .progress import ProgressCallback, ProgressUpdate
from .schemas import (
    ChapterAnchorsArtifact, CharactersArtifact, CraftAuditAnswer, CraftAuditArtifact,
    CraftContractArtifact,
    CraftRevisionAttempt, CraftRevisionHistory, IncrementalStorylineArtifact,
    LengthAuditArtifact, LengthAuditEntry, LLMUsageArtifact, StoryPlanArtifact,
    StoryRequest, StoryOutlineArtifact, WorldArtifact,
)
from .storage import ArtifactRepository


class StoryRun:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir

    @property
    def story_path(self) -> Path:
        return self.run_dir / "story.md"

    def __fspath__(self) -> str:
        return str(self.run_dir)


def _dump(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in value]
    return json.dumps(value, ensure_ascii=False, indent=2)


TArtifact = TypeVar("TArtifact", bound=BaseModel)


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
    """Public v2 API. Taxonomy retrieval guides planning but never prose directly."""

    def __init__(self, provider, output_root: Path, *, schema_repository: NarrativeSchemaRepository | None = None,
                 default_target_words: int = 1500, max_cpn_retries: int = 2,
                 max_craft_revisions: int = 2, max_artifact_retries: int = 2) -> None:
        if max_craft_revisions < 0 or max_artifact_retries < 0:
            raise ValueError("revision counts cannot be negative")
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
                    "Return a complete replacement, not a patch. The previous candidate was:\n"
                    f"{_dump(candidate)}\nVALIDATION ERROR:\n{issue}"
                )
        raise ArtifactValidationError(
            f"No se pudo obtener un artefacto {name} válido después de {attempts} intentos.",
            stage=stage,
            details={"artifact": name, "attempts": attempts, "validation_errors": issues},
            recommendations=[
                f"Revisa artifact_attempts/{name}/ y vuelve a intentarlo con un modelo más capaz."
            ],
        )

    @staticmethod
    def _validate_plan(plan: StoryPlanArtifact, blueprint: NarrativeBlueprint) -> None:
        allowed = {
            item.id for group in (
                blueprint.macroplots, blueprint.situations, blueprint.character_arcs,
            ) for item in group
        }
        selected = {plan.archetypes.primary, *plan.archetypes.secondary}
        unknown = selected - allowed
        if unknown:
            raise ValueError(f"unknown retrieved archetype IDs: {', '.join(sorted(unknown))}")

    @staticmethod
    def _validate_anchors(anchors: ChapterAnchorsArtifact, outline: StoryOutlineArtifact) -> None:
        expected = [chapter.id for chapter in outline.chapters]
        actual = [anchor.chapter_id for anchor in anchors.anchors]
        if len(actual) != len(set(actual)):
            raise ValueError("chapter anchor IDs must be unique")
        if set(actual) != set(expected) or len(actual) != len(expected):
            raise ValueError(
                "chapter anchors must match outline chapters exactly; "
                f"expected {expected}, received {actual}"
            )

    def _plan(self, request: StoryRequest, blueprint: NarrativeBlueprint,
              repair_feedback: str = "") -> StoryPlanArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Design a causal story plan from the request and retrieved narrative knowledge. "
                "Choose a small compatible composition rather than stacking labels. The protagonist's "
                "goal, mistaken belief or conviction, active opposition, irreversible choices, climax, "
                "and ending must form one causal argument. Use catalog IDs only for the archetype fields."
            ),
            prompt=(f"REQUEST:\n{_dump(request)}\nBLUEPRINT:\n{_dump(blueprint)}"
                    f"{repair_feedback}"),
            schema=StoryPlanArtifact,
        )

    def _world(self, request, plan) -> WorldArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Build a compact story world. Every rule and location must constrain a decision, "
                "create an opportunity, or cause a consequence. Avoid decorative lore."
            ), prompt=f"REQUEST:\n{_dump(request)}\nPLAN:\n{_dump(plan)}", schema=WorldArtifact)

    def _characters(self, request, plan, world, blueprint,
                    repair_feedback: str = "") -> CharactersArtifact:
        characters = self.provider.generate_structured(
            system_instruction=(
                "Create a compact cast with distinct goals. Every important action must be explainable "
                "by a character intention, and opposition must pursue an active incompatible goal. "
                "Use retrieved role IDs for jungian_archetype. Mark at least one character as main. "
                "Every main character must have sympathy, competence, and proactivity ranges from 1 "
                "to 10, one changing focus slider, an ascending or descending direction that matches "
                "that change, and a narrative justification. Supporting characters may omit sliders."
            ), prompt=(f"REQUEST:\n{_dump(request)}\nPLAN:\n{_dump(plan)}\nWORLD:\n{_dump(world)}"
                    f"\nROLES:\n{_dump(blueprint.roles)}{repair_feedback}"),
            schema=CharactersArtifact)
        return characters

    def _craft_contract(self, request, plan, world, characters,
                        repair_feedback: str = "") -> CraftContractArtifact:
        return CraftContractAgent(self.provider).run(
            request, plan, world, characters, repair_feedback=repair_feedback,
        )

    def _write_chapter(self, request, plan, world, characters, craft, storyline, nekg,
                       chapter, previous_text) -> str:
        nodes = [x for x in storyline.nodes if x.chapter_id == chapter.id]
        edges = [x for x in storyline.accepted_edges if x.source in {n.id for n in nodes} or x.target in {n.id for n in nodes}]
        return self.provider.generate_text(
            system_instruction=(
                "Write only the requested fiction chapter body in Markdown and in the requested language. "
                "Do not add a chapter title or heading; the orchestrator supplies the canonical title. "
                "Dramatize every accepted event in order while preserving intentions, causal effects, "
                "entity states and chapter ending. Hide all planning terminology. Use implication, "
                "subtext and scene-level variation so the result does not read like an outline. "
                "Dramatize assigned promise beats, slider milestones, and try-fail consequences through "
                "observable choices. Never mention craft IDs, slider names, or numeric values. Respect "
                "the approximate chapter word budget."
            ),
            prompt=(f"REQUEST:\n{_dump(request)}\nPLAN:\n{_dump(plan)}\nWORLD:\n{_dump(world)}\n"
                    f"CHARACTERS:\n{_dump(characters)}\nCRAFT CONTRACT:\n{_dump(craft)}\n"
                    f"CHAPTER:\n{_dump(chapter)}\nNODES:\n{_dump(nodes)}\n"
                    f"CAUSAL LINKS:\n{_dump(edges)}\nCURRENT NEKG:\n{_dump(nekg)}\n"
                    f"PREVIOUS CHAPTER TAIL:\n{previous_text[-6000:] if previous_text else 'none'}"),
        )

    def generate(self, request: StoryRequest | str, on_progress: ProgressCallback | None = None,
                 on_run_created=None) -> StoryRun:
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
            records = list(getattr(self.provider, "usage_records", []))[usage_start:]
            artifact = LLMUsageArtifact(
                records=records, calls=len(records),
                total_tokens=sum(item.total_tokens for item in records),
                total_wait_seconds=sum(item.wait_seconds for item in records),
            )
            repository.save_json("llm_usage.json", artifact)
            repository.save_json("llm_usage_summary.json", artifact)

        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = lambda _record: save_usage()
        try:
            repository.save_json("request.json", request)
            repository.complete_stage("analysis")
            blueprint = self.schemas.retrieve(request)
            repository.save_json("blueprint.json", blueprint)
            repository.save_json("retrieval_trace.json", blueprint.trace)
            repository.complete_stage("retrieval")
            notify(10, "retrieval", "Esquemas narrativos recuperados")

            plan = self._validated_artifact(
                repository, name="story_plan", stage="planning",
                generate=lambda feedback: self._plan(request, blueprint, feedback),
                validate=lambda value: self._validate_plan(value, blueprint),
            )
            repository.save_json("story_plan.json", plan)
            repository.complete_stage("story_plan")
            world = self._world(request, plan)
            repository.save_json("world.json", world)
            repository.complete_stage("world")
            characters = self._validated_artifact(
                repository, name="characters", stage="characters",
                generate=lambda feedback: self._characters(
                    request, plan, world, blueprint, feedback,
                ),
                validate=validate_craft_characters,
            )
            repository.save_json("characters.json", characters)
            repository.complete_stage("characters")
            craft = self._validated_artifact(
                repository, name="craft_contract", stage="craft_contract",
                generate=lambda feedback: self._craft_contract(
                    request, plan, world, characters, feedback,
                ),
                validate=lambda value: validate_craft_contract(
                    value, characters, request.target_words,
                ),
            )
            repository.save_json("craft_contract.json", craft)
            repository.complete_stage("craft_contract")
            planner = IncrementalPlotPlanner(self.provider, max_retries=self.max_cpn_retries)

            def validate_outline(value: StoryOutlineArtifact) -> None:
                validate_craft_outline(value, craft, characters)
                if sum(chapter.target_words for chapter in value.chapters) != request.target_words:
                    raise ValueError("chapter word budgets must equal requested target_words")

            outline = self._validated_artifact(
                repository, name="outline", stage="outline",
                generate=lambda feedback: planner.outline(
                    request, plan, blueprint, craft, characters, feedback,
                ),
                validate=validate_outline,
            )
            repository.save_json("outline.json", outline)
            repository.complete_stage("outline")
            anchors = self._validated_artifact(
                repository, name="chapter_anchors", stage="anchors",
                generate=lambda feedback: planner.anchors(
                    outline, world, characters, feedback,
                ),
                validate=lambda value: self._validate_anchors(value, outline),
            )
            repository.save_json("chapter_anchors.json", anchors)
            repository.complete_stage("anchors")
            notify(25, "outline", "Premisa, capítulos y anclas terminados")

            def save_planning_checkpoint(partial_storyline, partial_nekg, partial_reviews) -> None:
                repository.save_json("planning_checkpoint/storyline.json", partial_storyline)
                repository.save_json("planning_checkpoint/nekg.json", partial_nekg)
                repository.save_json("planning_checkpoint/node_reviews.json", partial_reviews)

            storyline, reviews = planner.plan(
                outline, anchors, blueprint, craft, characters,
                on_checkpoint=save_planning_checkpoint,
            )
            repository.save_json("storyline.json", storyline)
            repository.save_json("nekg.json", planner.nekg.artifact())
            repository.save_json("node_reviews.json", reviews)
            repository.complete_stage("storyline")
            notify(55, "storyline", "STORYLINE incremental validada")

            chapter_texts: list[str] = []
            total = len(outline.chapters)
            writing_nekg = NarrativeEntityGraph()
            changes_by_node = {record.node.id: record.state_changes for record in reviews.records}
            for index, chapter in enumerate(outline.chapters, 1):
                for node in (item for item in storyline.nodes if item.chapter_id == chapter.id):
                    writing_nekg.apply(node, changes_by_node.get(node.id, []))
                text = self._write_chapter(
                    request, plan, world, characters, craft, storyline,
                    writing_nekg.artifact(), chapter, "\n\n".join(chapter_texts),
                )
                text = _canonical_chapter(chapter.title, text)
                repository.save_text(f"chapters/chapter-{chapter.order:03d}.md", text)
                chapter_texts.append(text)
                notify(
                    55 + index * 35 // total, "chapters",
                    f"Capítulo {index} de {total} terminado", index, total,
                )
            draft = "\n\n".join(chapter_texts)
            repository.save_text("draft.md", draft)
            repository.complete_stage("draft")

            story, selected_audit, revision_history, warnings = self._review_draft(
                repository, request, craft, characters, outline, storyline, draft, notify,
            )
            repository.save_json("craft_revision_history.json", revision_history)
            repository.save_json("craft_audit.json", selected_audit)
            minimum, maximum = _length_bounds(request.target_words)
            actual_words = _word_count(story)
            repository.save_json("length_audit.json", LengthAuditArtifact(
                chapters=[], total=LengthAuditEntry(
                    target_words=request.target_words, minimum_words=minimum,
                    maximum_words=maximum, actual_words=actual_words,
                    within_tolerance=minimum <= actual_words <= maximum,
                ),
            ))
            repository.save_text("story.md", story)
            repository.save_json("diagnostic_audit.json", diagnostic_from_craft(selected_audit))
            if warnings:
                repository.save_data("quality_warning.json", {"warnings": warnings})
                for warning in warnings:
                    repository.add_warning(warning)
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

    def _review_draft(self, repository, request, craft, characters, outline,
                      storyline, draft, notify):
        critic = CraftCriticAgent(self.provider)
        rewriter = CraftRewriterAgent(self.provider)
        versions: list[tuple[int, str, CraftAuditArtifact, bool]] = []
        history_attempts: list[CraftRevisionAttempt] = []
        warnings: list[str] = []
        minimum, maximum = _length_bounds(request.target_words)
        notify(92, "craft_critic", "Auditando el borrador")
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
                    ) for question in audit_questions(craft, characters, outline)],
                )
            repository.save_json(audit_file, audit)
            advisory = [
                answer.question_id for answer in audit.answers
                if not answer.blocking and answer.verdict != "pass"
            ]
            history_attempts.append(CraftRevisionAttempt(
                attempt=attempt, text_file=text_file, audit_file=audit_file,
                passed=audit.passed and within_length,
                failed_blocking_ids=audit.failed_blocking_ids,
                failed_advisory_ids=advisory,
            ))
            versions.append((attempt, current_text, audit, within_length))
            if critic_failed or (audit.passed and within_length) or attempt == self.max_craft_revisions:
                break
            notify(
                94 + attempt * 2, "craft_rewriter",
                f"Aplicando revisión de craft {attempt + 1} de {self.max_craft_revisions}",
            )
            actual_words = _word_count(current_text)
            length_instruction = "" if within_length else (
                f"Rewrite the complete story to contain between {minimum} and {maximum} words; "
                f"the current version has {actual_words}."
            )
            try:
                current_text = rewriter.run(
                    request, craft, characters, outline, storyline, current_text, audit,
                    length_instruction=length_instruction,
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

        selected_attempt, story, selected_audit, within_length = min(
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
        history = CraftRevisionHistory(
            selected_attempt=selected_attempt, exhausted=exhausted,
            attempts=history_attempts,
        )
        return story, selected_audit, history, warnings

    def run(self, request: StoryRequest | str, on_progress: ProgressCallback | None = None,
            on_run_created=None) -> StoryRun:
        """Compatibility spelling used by the existing console and Telegram adapters."""
        return self.generate(request, on_progress=on_progress, on_run_created=on_run_created)

    def resume(self, run_id: str | Path, on_progress: ProgressCallback | None = None,
               on_run_created=None) -> StoryRun:
        run_dir = Path(run_id)
        if not run_dir.is_absolute():
            run_dir = self.output_root / run_dir
        if (run_dir / "story.md").is_file():
            return StoryRun(run_dir)
        request = StoryRequest.model_validate_json((run_dir / "request.json").read_text(encoding="utf-8"))
        # Failed partial runs remain auditable; restart creates a fresh run instead of mixing states.
        return self.generate(request, on_progress=on_progress, on_run_created=on_run_created)
