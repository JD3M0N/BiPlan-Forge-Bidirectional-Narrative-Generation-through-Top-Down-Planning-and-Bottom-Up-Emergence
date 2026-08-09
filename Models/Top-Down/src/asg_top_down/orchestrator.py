"""Explicit orchestration for the STORYTELLER-style Top-Down pipeline."""

from pathlib import Path

from asg_evaluation import create_evaluation_template

from .agents import (
    AnalystAgent, ChapterComplianceAgent, CharacterDesignerAgent, CriticAgent,
    DirectorAgent, DramaAgent, EditorAgent, PlannerAgent, SceneWriterAgent,
    WorldBuilderAgent,
)
from .graph import StorylineGraphProcessor, StorylineValidationError, render_mermaid
from .nekg import NarrativeEntityGraph
from .provider import LanguageModelProvider
from .schemas import (
    NodeReview, NodeReviewsArtifact, ReplanningAttempt, ReplanningHistoryArtifact,
)
from .storage import ArtifactRepository
from .taxonomies import TaxonomyRepository


def _chapter_filename(order: int) -> str:
    return f"scenes/chapter-{order:03d}.md"


def _continuity_context(text: str, limit: int = 6000) -> str:
    return text[-limit:]


def _word_count(text: str) -> int:
    return len(text.split())


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
        raise StorylineValidationError(["No valid CBN-CPN-CEN DAG after five replanning attempts", *diagnostics])

    def run(self, prompt: str) -> Path:
        request = self.analyst.run(prompt)
        repository = ArtifactRepository(self.output_root, self.provider.model_name, request.title)
        try:
            repository.save_json("request.json", request)
            repository.complete_stage("analyst")
            plan = self.planner.run(request)
            repository.save_json("archetypes.json", plan.archetypes)
            repository.save_json("story_plan.json", plan)
            repository.complete_stage("planner")
            world = self.world_builder.run(request, plan)
            repository.save_json("world.json", world)
            repository.complete_stage("world")
            characters = self.character_designer.run(request, plan, world)
            repository.save_json("characters.json", characters)
            repository.complete_stage("characters")

            archetype_ids = [plan.archetypes.primary, *plan.archetypes.secondary]
            archetypes = self.taxonomies.get_archetypes(archetype_ids)
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
            for chapter in graph.chapters:
                prior = _continuity_context("\n\n".join(chapter_texts))
                revision = ""
                text = ""
                for write_attempt in range(3):
                    text = self.chapter_writer.run(
                        request, plan, world, characters, graph, chapter, prior, revision,
                    )
                    audit = self.compliance.run(chapter, graph, text)
                    actual = _word_count(text)
                    tolerance_ok = chapter.target_words * .9 <= actual <= chapter.target_words * 1.1
                    covered = {x.id for x in graph.nodes if x.chapter_id == chapter.id}.issubset(audit.covered_node_ids)
                    if audit.passed and tolerance_ok and covered:
                        break
                    revision = "; ".join([
                        *audit.issues, *audit.revision_instructions,
                        f"Conteo real {actual}; objetivo {chapter.target_words} (±10%).",
                    ])
                else:
                    raise ValueError(f"Chapter {chapter.id} failed words or goal coverage after two rewrites")
                repository.save_text(_chapter_filename(chapter.order), text)
                chapter_texts.append(text.strip())
            draft = "\n\n".join(chapter_texts)
            repository.save_text("draft.md", draft)
            repository.complete_stage("scenes")

            story_drama = self.drama.run(graph, draft)
            if not story_drama.passed:
                for _ in range(2):
                    correction = "; ".join(story_drama.revision_instructions or story_drama.issues)
                    # Correct the complete prose while preserving the validated DAG.
                    provisional_review = self.critic.run(request, plan, graph, draft)
                    provisional_review.revision_instructions.extend([correction])
                    draft = self.editor.run(request, plan, graph, draft, provisional_review)
                    story_drama = self.drama.run(graph, draft)
                    if story_drama.passed:
                        break
            if not story_drama.passed:
                raise ValueError("Story failed Freytag verification after two correction cycles")

            review = self.critic.run(request, plan, graph, draft)
            repository.save_json("review.json", review)
            repository.complete_stage("review")
            correction = ""
            story = draft
            for _ in range(3):
                story = self.editor.run(request, plan, graph, story, review, correction)
                total = _word_count(story)
                final_drama = self.drama.run(graph, story)
                length_ok = request.target_words * .95 <= total <= request.target_words * 1.05
                if length_ok and final_drama.passed:
                    break
                correction = "; ".join([
                    *final_drama.issues, *final_drama.revision_instructions,
                    f"Conteo {total}; ajustar al objetivo {request.target_words} ±5%.",
                ])
            else:
                raise ValueError("Final story failed Freytag or global word target after two corrections")
            repository.save_json("freytag_story_review.json", final_drama)
            repository.save_text("story.md", story)
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("story")
            repository.complete()
            return repository.run_dir
        except Exception as exc:
            repository.fail(str(exc))
            raise
