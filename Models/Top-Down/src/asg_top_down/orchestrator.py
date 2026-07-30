"""Orquestación explícita del flujo Top-Down."""

from pathlib import Path

from asg_evaluation import create_evaluation_template

from .agents import (
    AnalystAgent,
    CharacterDesignerAgent,
    CriticAgent,
    EditorAgent,
    PlotArchitectAgent,
    WorldBuilderAgent,
    WriterAgent,
)
from .provider import LanguageModelProvider
from .storage import ArtifactRepository


class StoryOrchestrator:
    def __init__(self, provider: LanguageModelProvider, output_root: Path) -> None:
        self.provider = provider
        self.output_root = output_root
        self.analyst = AnalystAgent(provider)
        self.world_builder = WorldBuilderAgent(provider)
        self.character_designer = CharacterDesignerAgent(provider)
        self.plot_architect = PlotArchitectAgent(provider)
        self.writer = WriterAgent(provider)
        self.critic = CriticAgent(provider)
        self.editor = EditorAgent(provider)

    def run(self, prompt: str) -> Path:
        request = self.analyst.run(prompt)
        repository = ArtifactRepository(
            self.output_root, self.provider.model_name, request.title
        )
        try:
            repository.save_json("request.json", request)
            repository.complete_stage("analyst")

            world = self.world_builder.run(request)
            repository.save_json("world.json", world)
            repository.complete_stage("world")

            characters = self.character_designer.run(request, world)
            repository.save_json("characters.json", characters)
            repository.complete_stage("characters")

            outline = self.plot_architect.run(request, world, characters)
            repository.save_json("outline.json", outline)
            repository.complete_stage("outline")

            draft = self.writer.run(request, world, characters, outline)
            repository.save_text("draft.md", draft)
            repository.complete_stage("draft")

            review = self.critic.run(request, outline, draft)
            repository.save_json("review.json", review)
            repository.complete_stage("review")

            story = self.editor.run(request, outline, draft, review)
            repository.save_text("story.md", story)
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("story")
            repository.complete()
            return repository.run_dir
        except Exception as exc:
            repository.fail(str(exc))
            raise
