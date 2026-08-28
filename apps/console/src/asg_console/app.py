"""Application coordinator for the unified ASG console."""

from __future__ import annotations

import argparse

from .bottom_up import BottomUpMenu
from .evaluation import EvaluationMenu
from .top_down import TopDownMenu
from .types import InputFn, OutputFn


class ConsoleApp:
    """Coordinate navigation among model and evaluation menus."""

    def __init__(
        self,
        input_fn: InputFn = input,
        output: OutputFn = print,
        top_down: TopDownMenu | None = None,
        bottom_up: BottomUpMenu | None = None,
        evaluation: EvaluationMenu | None = None,
    ) -> None:
        """Configure console I/O and injectable menu collaborators."""
        self.input = input_fn
        self.output = output
        self.top_down = top_down or TopDownMenu(input_fn, output)
        self.bottom_up = bottom_up or BottomUpMenu(input_fn, output)
        self.evaluation = evaluation or EvaluationMenu(input_fn, output)

    def run(self) -> int:
        """Display the main menu until exit or input cancellation."""
        self.output("Automatic Story Generation — Consola unificada")
        while True:
            self.output(
                "\nMenú principal\n  1. Top-Down\n  2. Bottom-Up\n  3. Evaluar historia\n  0. Salir"
            )
            try:
                choice = self.input("> ").strip()
                if choice == "0":
                    self.output("Hasta luego.")
                    return 0
                actions = {
                    "1": self.top_down.run,
                    "2": self.bottom_up.run,
                    "3": self._evaluate_story,
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
    parser().parse_args(argv)
    return ConsoleApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
