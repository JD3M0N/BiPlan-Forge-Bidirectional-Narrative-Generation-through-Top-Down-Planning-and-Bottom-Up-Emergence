"""Interactive console workflow for evaluating stored stories."""

from __future__ import annotations

from asg_core import find_project_root
from asg_evaluation import METRICS, add_evaluation, discover_stories

from .types import InputFn, OutputFn


class EvaluationMenu:
    """Collect and persist one complete human story evaluation."""

    def __init__(self, input_fn: InputFn = input, output: OutputFn = print) -> None:
        """Configure console input and output functions."""
        self.input = input_fn
        self.output = output

    def run(self) -> None:
        """Select a story, collect scores, and persist the evaluation."""
        root = find_project_root()
        stories_root = root / "Stories"
        stories = discover_stories(stories_root)
        if not stories:
            self.output("No hay historias disponibles para evaluar.")
            return
        self.output("\nHistorias disponibles")
        for index, directory in enumerate(stories, start=1):
            self.output(f"  {index}. {directory.relative_to(stories_root)}")
        self.output("  0. Cancelar")
        selected = self._story_choice(len(stories))
        if selected is None:
            return
        user = self._evaluator_name()
        scores = {metric: self._score(metric) for metric in METRICS}
        destination = add_evaluation(stories[selected], user, scores)
        self.output(f"Evaluación guardada en: {destination}")

    def _evaluator_name(self) -> str:
        """Prompt until a non-empty evaluator name is entered."""
        user = self.input("Usuario evaluador: ").strip()
        while not user:
            self.output("El usuario no puede estar vacío.")
            user = self.input("Usuario evaluador: ").strip()
        return user

    def _story_choice(self, count: int) -> int | None:
        """Prompt for a valid story index or a cancellation."""
        while True:
            value = self.input("Selecciona una historia: ").strip()
            try:
                selected = int(value)
            except ValueError:
                selected = -1
            if selected == 0:
                return None
            if 1 <= selected <= count:
                return selected - 1
            self.output("Selección inválida.")

    def _score(self, metric: str) -> int:
        """Prompt until a score from one through ten is entered."""
        while True:
            value = self.input(f"{metric} [1-10]: ").strip()
            try:
                score = int(value)
            except ValueError:
                score = 0
            if 1 <= score <= 10:
                return score
            self.output("Introduce un entero entre 1 y 10.")
