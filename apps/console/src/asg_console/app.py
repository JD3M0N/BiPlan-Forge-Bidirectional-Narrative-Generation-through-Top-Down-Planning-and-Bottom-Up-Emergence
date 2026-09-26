"""Application coordinator for the unified ASG console."""

from __future__ import annotations

import argparse

from asg_core import use_utf8_output

from .evaluation import EvaluationMenu
from .stagecraft import StagecraftMenu
from .types import InputFn, OutputFn


class ConsoleApp:
    """Coordinate navigation between story generation and evaluation."""

    def __init__(
        self,
        input_fn: InputFn = input,
        output: OutputFn = print,
        stagecraft: StagecraftMenu | None = None,
        evaluation: EvaluationMenu | None = None,
    ) -> None:
        """Configure console I/O and injectable menu collaborators."""
        self.input = input_fn
        self.output = output
        self.stagecraft = stagecraft or StagecraftMenu(input_fn, output)
        self.evaluation = evaluation or EvaluationMenu(input_fn, output)

    def run(self) -> int:
        """Display the main menu until exit or input cancellation."""
        self.output("Automatic Story Generation — Consola unificada")
        while True:
            self.output("\nMenú principal\n  1. Stagecraft\n  2. Evaluar historia\n  0. Salir")
            try:
                choice = self.input("> ").strip()
                if choice == "0":
                    self.output("Hasta luego.")
                    return 0
                actions = {
                    "1": self.stagecraft.run,
                    "2": self._evaluate_story,
                }
                action = actions.get(choice)
                if action:
                    action()
                else:
                    self.output("Opción inválida.")
            except (EOFError, KeyboardInterrupt):
                self.output("\nOperación cancelada.")
                return 1
            except Exception as exc:
                self.output(f"Error: {exc}")

    def _evaluate_story(self) -> None:
        """Delegate story evaluation to the focused evaluation menu."""
        self.evaluation.run()


def parser() -> argparse.ArgumentParser:
    """Build the unified-console command-line parser."""
    return argparse.ArgumentParser(description="Abre la consola unificada de ASG")


def main(argv: list[str] | None = None) -> int:
    """Run the console application and return its process status."""
    use_utf8_output()
    parser().parse_args(argv)
    return ConsoleApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
