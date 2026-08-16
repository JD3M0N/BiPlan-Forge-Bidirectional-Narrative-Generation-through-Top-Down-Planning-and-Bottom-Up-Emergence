"""Production STORYTELLER generator built around incremental accepted events."""

from __future__ import annotations

from pathlib import Path
import json

from pydantic import BaseModel

from asg_evaluation import create_evaluation_template

from .agents.analyst import AnalystAgent
from .agents.craft import CraftContractAgent, CraftCriticAgent, CraftRewriterAgent
from .craft import (
    diagnostic_from_craft, validate_craft_characters, validate_craft_contract,
)
from .incremental import IncrementalPlotPlanner
from .narrative_db import NarrativeBlueprint, NarrativeSchemaRepository
from .nekg import NarrativeEntityGraph
from .progress import ProgressCallback, ProgressUpdate
from .schemas import (
    CharactersArtifact, CraftAuditArtifact, CraftContractArtifact,
    CraftRevisionAttempt, CraftRevisionHistory, IncrementalStorylineArtifact,
    StoryPlanArtifact, StoryRequest, StoryOutlineArtifact, WorldArtifact,
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


class StoryGenerator:
    """Public v2 API. Taxonomy retrieval guides planning but never prose directly."""

    def __init__(self, provider, output_root: Path, *, schema_repository: NarrativeSchemaRepository | None = None,
                 default_target_words: int = 1500, max_cpn_retries: int = 2,
                 max_craft_revisions: int = 2) -> None:
        if max_craft_revisions < 0:
            raise ValueError("max_craft_revisions cannot be negative")
        self.provider = provider
        self.output_root = Path(output_root)
        self.default_target_words = default_target_words
        self.schemas = schema_repository or NarrativeSchemaRepository(provider=provider)
        self.max_cpn_retries = max_cpn_retries
        self.max_craft_revisions = max_craft_revisions

    def _notify(self, callback, percent, stage, description, chapter=None, total=None) -> None:
        if callback:
            callback(ProgressUpdate(percent, stage, description, chapter, total))

    def _plan(self, request: StoryRequest, blueprint: NarrativeBlueprint) -> StoryPlanArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Design a causal story plan from the request and retrieved narrative knowledge. "
                "Choose a small compatible composition rather than stacking labels. The protagonist's "
                "goal, mistaken belief or conviction, active opposition, irreversible choices, climax, "
                "and ending must form one causal argument. Use catalog IDs only for the archetype fields."
            ),
            prompt=f"REQUEST:\n{_dump(request)}\nBLUEPRINT:\n{_dump(blueprint)}",
            schema=StoryPlanArtifact,
        )

    def _world(self, request, plan) -> WorldArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Build a compact story world. Every rule and location must constrain a decision, "
                "create an opportunity, or cause a consequence. Avoid decorative lore."
            ), prompt=f"REQUEST:\n{_dump(request)}\nPLAN:\n{_dump(plan)}", schema=WorldArtifact)

    def _characters(self, request, plan, world, blueprint) -> CharactersArtifact:
        characters = self.provider.generate_structured(
            system_instruction=(
                "Create a compact cast with distinct goals. Every important action must be explainable "
                "by a character intention, and opposition must pursue an active incompatible goal. "
                "Use retrieved role IDs for jungian_archetype. Mark at least one character as main. "
                "Every main character must have sympathy, competence, and proactivity ranges from 1 "
                "to 10, one changing focus slider, an ascending or descending direction that matches "
                "that change, and a narrative justification. Supporting characters may omit sliders."
            ), prompt=f"REQUEST:\n{_dump(request)}\nPLAN:\n{_dump(plan)}\nWORLD:\n{_dump(world)}\nROLES:\n{_dump(blueprint.roles)}",
            schema=CharactersArtifact)
        validate_craft_characters(characters)
        return characters

    def _craft_contract(self, request, plan, world, characters) -> CraftContractArtifact:
        contract = CraftContractAgent(self.provider).run(request, plan, world, characters)
        validate_craft_contract(contract, characters, request.target_words)
        return contract

    def _write_chapter(self, request, plan, world, characters, craft, storyline, nekg,
                       chapter, previous_text) -> str:
        nodes = [x for x in storyline.nodes if x.chapter_id == chapter.id]
        edges = [x for x in storyline.accepted_edges if x.source in {n.id for n in nodes} or x.target in {n.id for n in nodes}]
        return self.provider.generate_text(
            system_instruction=(
                "Write only the requested fiction chapter in Markdown and in the requested language. "
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
        self._notify(on_progress, 0, "analysis", "Analizando la solicitud")
        if isinstance(request, str):
            request = AnalystAgent(self.provider, self.default_target_words).run(request)
        repository = ArtifactRepository(self.output_root, self.provider.model_name, request.title)
        if on_run_created:
            on_run_created(repository.run_dir)
        try:
            repository.save_json("request.json", request)
            blueprint = self.schemas.retrieve(request)
            repository.save_json("blueprint.json", blueprint)
            repository.save_json("retrieval_trace.json", blueprint.trace)
            self._notify(on_progress, 10, "retrieval", "Esquemas narrativos recuperados")
            plan = self._plan(request, blueprint); repository.save_json("story_plan.json", plan)
            world = self._world(request, plan); repository.save_json("world.json", world)
            characters = self._characters(request, plan, world, blueprint); repository.save_json("characters.json", characters)
            craft = self._craft_contract(request, plan, world, characters)
            repository.save_json("craft_contract.json", craft)
            planner = IncrementalPlotPlanner(self.provider, max_retries=self.max_cpn_retries)
            outline = planner.outline(request, plan, blueprint, craft, characters)
            if sum(x.target_words for x in outline.chapters) != request.target_words:
                raise ValueError("chapter word budgets must equal requested target_words")
            repository.save_json("outline.json", outline)
            anchors = planner.anchors(outline, world, characters); repository.save_json("chapter_anchors.json", anchors)
            self._notify(on_progress, 25, "outline", "Premisa, capítulos y anclas terminados")
            storyline, reviews = planner.plan(outline, anchors, blueprint, craft, characters)
            repository.save_json("storyline.json", storyline)
            repository.save_json("nekg.json", planner.nekg.artifact())
            repository.save_json("node_reviews.json", reviews)
            self._notify(on_progress, 55, "storyline", "STORYLINE incremental validada")
            chapter_texts: list[str] = []
            total = len(outline.chapters)
            writing_nekg = NarrativeEntityGraph()
            changes_by_node = {record.node.id: record.state_changes for record in reviews.records}
            for index, chapter in enumerate(outline.chapters, 1):
                for node in (x for x in storyline.nodes if x.chapter_id == chapter.id):
                    writing_nekg.apply(node, changes_by_node.get(node.id, []))
                text = self._write_chapter(request, plan, world, characters, craft, storyline,
                                           writing_nekg.artifact(), chapter, "\n\n".join(chapter_texts))
                repository.save_text(f"chapters/chapter-{chapter.order:03d}.md", text)
                chapter_texts.append(text.strip())
                self._notify(on_progress, 55 + index * 35 // total, "chapters",
                             f"Capítulo {index} de {total} terminado", index, total)
            draft = "\n\n".join(chapter_texts)
            repository.save_text("draft.md", draft)
            critic = CraftCriticAgent(self.provider)
            rewriter = CraftRewriterAgent(self.provider)
            versions: list[tuple[int, str, CraftAuditArtifact]] = []
            history_attempts: list[CraftRevisionAttempt] = []

            self._notify(on_progress, 92, "craft_critic", "Auditando el borrador")
            current_text = draft
            for attempt in range(self.max_craft_revisions + 1):
                text_file = f"craft_revisions/attempt-{attempt}.md"
                audit_file = f"craft_revisions/attempt-{attempt}-audit.json"
                repository.save_text(text_file, current_text)
                audit = critic.run(request, craft, characters, outline, storyline, current_text)
                repository.save_json(audit_file, audit)
                advisory = [answer.question_id for answer in audit.answers
                            if not answer.blocking and answer.verdict != "pass"]
                history_attempts.append(CraftRevisionAttempt(
                    attempt=attempt, text_file=text_file, audit_file=audit_file,
                    passed=audit.passed, failed_blocking_ids=audit.failed_blocking_ids,
                    failed_advisory_ids=advisory,
                ))
                versions.append((attempt, current_text, audit))
                if audit.passed or attempt == self.max_craft_revisions:
                    break
                self._notify(
                    on_progress,
                    94 + attempt * 2,
                    "craft_rewriter",
                    f"Aplicando revisión de craft {attempt + 1} de {self.max_craft_revisions}",
                )
                current_text = rewriter.run(
                    request, craft, characters, outline, storyline, current_text, audit,
                )

            selected_attempt, story, selected_audit = min(
                versions,
                key=lambda item: (
                    len(item[2].failed_blocking_ids),
                    sum(not answer.blocking and answer.verdict != "pass"
                        for answer in item[2].answers),
                    -item[0],
                ),
            )
            revision_history = CraftRevisionHistory(
                selected_attempt=selected_attempt,
                exhausted=not any(item[2].passed for item in versions),
                attempts=history_attempts,
            )
            repository.save_json("craft_revision_history.json", revision_history)
            repository.save_json("craft_audit.json", selected_audit)
            repository.save_text("story.md", story)
            repository.save_json("diagnostic_audit.json", diagnostic_from_craft(selected_audit))
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("story"); repository.complete()
            self._notify(on_progress, 100, "completed", "Historia terminada")
            return StoryRun(repository.run_dir)
        except Exception as exc:
            repository.fail(exc)
            raise

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
