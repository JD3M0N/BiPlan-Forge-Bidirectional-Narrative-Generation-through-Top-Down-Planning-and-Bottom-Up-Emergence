"""Explicit orchestration for the Top-Down v2 pipeline."""

from pathlib import Path

from asg_evaluation import create_evaluation_template

from .agents import (
    AnalystAgent,
    CharacterDesignerAgent,
    CriticAgent,
    DirectorAgent,
    EditorAgent,
    PlannerAgent,
    SceneWriterAgent,
    WorldBuilderAgent,
)
from .graph import CausalGraphProcessor, render_mermaid
from .provider import LanguageModelProvider
from .storage import ArtifactRepository
from .taxonomies import TaxonomyRepository


def _scene_filename(order: int) -> str:
    return f"scenes/scene-{order:03d}.md"


def _continuity_context(text: str, limit: int = 6000) -> str:
    """Bound accumulated context while retaining the most recent prose."""
    return text[-limit:]


class StoryOrchestrator:
    def __init__(
        self,
        provider: LanguageModelProvider,
        output_root: Path,
        taxonomy_root: Path | None = None,
    ) -> None:
        self.provider = provider
        self.output_root = output_root
        self.taxonomies = TaxonomyRepository(taxonomy_root)
        self.analyst = AnalystAgent(provider)
        self.planner = PlannerAgent(provider, self.taxonomies)
        self.world_builder = WorldBuilderAgent(provider)
        self.character_designer = CharacterDesignerAgent(provider, self.taxonomies)
        self.director = DirectorAgent(provider)
        self.graph_processor = CausalGraphProcessor()
        self.scene_writer = SceneWriterAgent(provider)
        self.critic = CriticAgent(provider)
        self.editor = EditorAgent(provider)

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

            directed = self.director.run(request, plan, world, characters)
            repository.complete_stage("director")
            graph = self.graph_processor.process(directed)
            repository.save_json("narrative_graph.json", graph)
            repository.save_text("narrative_graph.md", render_mermaid(graph))
            repository.complete_stage("graph")

            scene_texts: list[str] = []
            for scene in sorted(graph.scenes, key=lambda item: item.order):
                prior = _continuity_context("\n\n".join(scene_texts))
                text = self.scene_writer.run(request, plan, world, characters, graph, scene, prior)
                repository.save_text(_scene_filename(scene.order), text)
                scene_texts.append(text.strip())
            draft = "\n\n".join(scene_texts)
            repository.save_text("draft.md", draft)
            repository.complete_stage("scenes")

            review = self.critic.run(request, plan, graph, draft)
            repository.save_json("review.json", review)
            repository.complete_stage("review")

            story = self.editor.run(request, plan, graph, draft, review)
            repository.save_text("story.md", story)
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("story")
            repository.complete()
            return repository.run_dir
        except Exception as exc:
            repository.fail(str(exc))
            raise
