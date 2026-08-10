"""Menús de navegación para los modelos ASG."""

from __future__ import annotations

import argparse
import inspect
import secrets
import sys
from pathlib import Path
from typing import Callable

from asg_evaluation import (
    METRICS,
    add_evaluation,
    create_evaluation_template,
    discover_stories,
)
from asg_escape_room.cli import room_with_agents, run_batch, run_one
from asg_escape_room.config import find_project_root
from asg_escape_room.config import load_settings as load_bottom_up_settings
from asg_escape_room.engine import EscapeRoomModel
from asg_escape_room.narrative import (
    GeminiNarrativeProvider,
    generate_story,
)
from asg_escape_room.storage import RunRepository
from asg_prompt_crafter import CraftResult, PromptCrafterAgent
from asg_top_down.config import load_settings as load_top_down_settings
from asg_top_down.orchestrator import StoryOrchestrator
from asg_top_down.progress import format_progress
from asg_top_down.provider import GeminiProvider

from .visualizer import EscapeRoomVisualizer

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


class TopDownMenu:
    def __init__(self, input_fn: InputFn = input, output: OutputFn = print) -> None:
        self.input = input_fn
        self.output = output

    def run(self) -> None:
        while True:
            self.output("\nTop-Down\n  1. Generate story\n  0. Volver")
            choice = self.input("> ").strip()
            if choice == "0":
                return
            if choice != "1":
                self.output("Opción inválida.")
                continue
            prompt_mode = self._prompt_mode()
            if prompt_mode is None:
                continue
            if prompt_mode == "manual":
                prompt = self.input("Describe la historia:\n> ").strip()
                if not prompt:
                    self.output("El prompt no puede estar vacío.")
                    continue
            settings = load_top_down_settings()
            provider = GeminiProvider(settings.api_key, settings.model)
            if prompt_mode == "assisted":
                prompt = self._assisted_prompt(provider)
                if prompt is None:
                    continue
            self.output(f"Generando con {settings.model}...")
            orchestrator = StoryOrchestrator(
                provider, settings.output_root,
                default_target_words=settings.default_target_words,
            )
            if "on_progress" in inspect.signature(orchestrator.run).parameters:
                output = orchestrator.run(
                    prompt,
                    on_progress=lambda update: self.output(format_progress(update)),
                )
            else:
                output = orchestrator.run(prompt)
            self.output(f"Historia terminada: {output / 'story.md'}")

    def _prompt_mode(self) -> str | None:
        while True:
            self.output(
                "\n¿Cómo quieres crear el prompt?\n"
                "  1. Prompt asistido (3 alternativas)\n"
                "  2. Prompt manual\n"
                "  0. Cancelar"
            )
            choice = self.input("> ").strip()
            if choice == "1":
                return "assisted"
            if choice == "2":
                return "manual"
            if choice == "0":
                return None
            self.output("Opción inválida.")

    def _assisted_prompt(self, provider: GeminiProvider) -> str | None:
        idea = self.input("Describe la idea inicial de la historia:\n> ").strip()
        if not idea:
            self.output("El prompt no puede estar vacío.")
            return None
        self.output(f"Creando 3 alternativas con {provider.model_name}...")
        result = PromptCrafterAgent(provider).craft(idea)
        self._show_alternatives(result)
        while True:
            choice = self.input("Elige un prompt [1-3] o 0 para cancelar: ").strip()
            if choice == "0":
                return None
            try:
                index = int(choice) - 1
            except ValueError:
                index = -1
            if 0 <= index < len(result.alternatives):
                selected = result.alternatives[index]
                self.output(f"Prompt seleccionado: {selected.name}")
                return selected.prompt
            self.output("Selección inválida.")

    def _show_alternatives(self, result: CraftResult) -> None:
        self.output("\nAlternativas mejoradas")
        for index, alternative in enumerate(result.alternatives, start=1):
            recommended = (
                " — RECOMENDADA"
                if alternative.id == result.recommended_id
                else ""
            )
            self.output(
                f"\n{index}. {alternative.name} [{alternative.id}]"
                f"{recommended}\n"
                f"Enfoque: {alternative.creative_direction}\n\n"
                f"{alternative.prompt}"
            )
        self.output(f"\nRecomendación: {result.recommendation_reason}")


class BottomUpMenu:
    def __init__(
        self,
        input_fn: InputFn = input,
        output: OutputFn = print,
        visualizer_factory: Callable[..., EscapeRoomVisualizer] = (
            EscapeRoomVisualizer
        ),
    ) -> None:
        self.input = input_fn
        self.output = output
        self.visualizer_factory = visualizer_factory
        root = find_project_root()
        self.default_map = (
            root
            / "Models"
            / "Bottom-Up"
            / "escape-room"
            / "maps"
            / "escape_room.json"
        )

    def run(self) -> None:
        while True:
            self.output(
                "\nBottom-Up\n"
                "  1. Escape room normal\n"
                "  2. Experimento batch (60 simulaciones)\n"
                "  3. Escape Room Visual\n"
                "  0. Volver"
            )
            choice = self.input("> ").strip()
            if choice == "0":
                return
            if choice == "1":
                self._normal()
            elif choice == "2":
                self._batch()
            elif choice == "3":
                self._visual()
            else:
                self.output("Opción inválida.")

    def _normal(self) -> None:
        args = self._simulation_options()
        output = run_one(args)
        self.output(f"Resultado guardado en: {output}")

    def _batch(self) -> None:
        map_path = self._map()
        tick_limit = self._integer(
            "Límite de ticks [300]: ", default=300, minimum=1
        )
        args = argparse.Namespace(
            map=map_path,
            seed=None,
            agents=2,
            tick_limit=tick_limit,
            batch=True,
            no_llm=True,
        )
        output = run_batch(args)
        self.output(f"Experimento guardado en: {output}")

    def _visual(self) -> None:
        args = self._simulation_options()
        interval = self._float(
            "Intervalo entre ticks en segundos [1.5]: ",
            default=1.5,
            minimum=0.1,
            maximum=5.0,
        )
        seed = args.seed if args.seed is not None else secrets.randbits(64)
        room = room_with_agents(args.map, args.agents)
        model = EscapeRoomModel(room, seed)
        outcome = self.visualizer_factory(interval=interval).run(
            model, tick_limit=args.tick_limit
        )
        if outcome.cancelled:
            self.output("Visualización descartada; no se guardaron archivos.")
            return
        output = self._save_visual(
            args=args, seed=seed, room=room, model=outcome.model
        )
        result = outcome.result
        self.output(
            f"Simulación terminada: "
            f"{'escape exitoso' if result and result.success else 'límite alcanzado'}."
        )
        self.output(f"Resultado guardado en: {output}")
        self.input("Pulsa Enter para volver al menú...")

    def _save_visual(self, *, args, seed, room, model) -> Path:
        settings = load_bottom_up_settings()
        repository = RunRepository(
            settings.output_root, room.name, settings.model
        )
        try:
            repository.save_json(
                "request.json",
                {
                    "map": str(args.map.resolve()),
                    "seed": seed,
                    "agents": args.agents,
                    "tick_limit": args.tick_limit,
                    "mode": "visual",
                },
            )
            repository.save_json("initial_world.json", room)
            repository.save_json(
                "characters.json",
                [agent.model_dump(mode="json") for agent in room.agents],
            )
            repository.complete_stage("configuration")
            result = model.result()
            repository.save_ticks(model.tick_records)
            repository.save_json("events.json", model.event_log)
            repository.save_json("result.json", result)
            repository.save_json("metrics.json", result.metrics)
            repository.complete_stage("simulation")
            provider = None
            if not args.no_llm and settings.api_key:
                provider = GeminiNarrativeProvider(
                    settings.api_key, settings.model
                )
            story, narrator, error = generate_story(
                result, model.event_log, provider
            )
            repository.save_text("story.md", story)
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("narrative")
            repository.complete(narrator, error)
            return repository.run_dir
        except Exception as exc:
            repository.fail(str(exc))
            raise

    def _simulation_options(self) -> argparse.Namespace:
        map_path = self._map()
        agents = self._integer(
            "Número de agentes, 2 o 3 [2]: ",
            default=2,
            allowed={2, 3},
        )
        seed_text = self.input(
            "Semilla reproducible [aleatoria]: "
        ).strip()
        while seed_text and not self._is_integer(seed_text):
            self.output("Introduce un número entero o deja el campo vacío.")
            seed_text = self.input(
                "Semilla reproducible [aleatoria]: "
            ).strip()
        seed = int(seed_text) if seed_text else None
        tick_limit = self._integer(
            "Límite de ticks [300]: ", default=300, minimum=1
        )
        use_llm = self._yes_no("¿Generar relato con Gemini? [S/n]: ", True)
        return argparse.Namespace(
            map=map_path,
            seed=seed,
            agents=agents,
            tick_limit=tick_limit,
            batch=False,
            no_llm=not use_llm,
        )

    def _map(self) -> Path:
        value = self.input(
            f"Mapa [{self.default_map}]: "
        ).strip()
        path = Path(value) if value else self.default_map
        while not path.is_file():
            self.output("El mapa indicado no existe.")
            value = self.input(
                f"Mapa [{self.default_map}]: "
            ).strip()
            path = Path(value) if value else self.default_map
        return path

    def _integer(
        self,
        prompt: str,
        *,
        default: int,
        minimum: int | None = None,
        allowed: set[int] | None = None,
    ) -> int:
        while True:
            value = self.input(prompt).strip()
            if not value:
                return default
            if self._is_integer(value):
                number = int(value)
                if (minimum is None or number >= minimum) and (
                    allowed is None or number in allowed
                ):
                    return number
            self.output("Valor inválido.")

    def _float(
        self,
        prompt: str,
        *,
        default: float,
        minimum: float,
        maximum: float,
    ) -> float:
        while True:
            value = self.input(prompt).strip()
            if not value:
                return default
            try:
                number = float(value)
            except ValueError:
                number = minimum - 1
            if minimum <= number <= maximum:
                return number
            self.output(
                f"Introduce un número entre {minimum} y {maximum}."
            )

    def _yes_no(self, prompt: str, default: bool) -> bool:
        while True:
            value = self.input(prompt).strip().lower()
            if not value:
                return default
            if value in {"s", "si", "sí", "y", "yes"}:
                return True
            if value in {"n", "no"}:
                return False
            self.output("Responde S o N.")

    @staticmethod
    def _is_integer(value: str) -> bool:
        try:
            int(value)
            return True
        except ValueError:
            return False


class ConsoleApp:
    def __init__(
        self,
        input_fn: InputFn = input,
        output: OutputFn = print,
        top_down: TopDownMenu | None = None,
        bottom_up: BottomUpMenu | None = None,
    ) -> None:
        self.input = input_fn
        self.output = output
        self.top_down = top_down or TopDownMenu(input_fn, output)
        self.bottom_up = bottom_up or BottomUpMenu(input_fn, output)

    def run(self) -> int:
        self.output("Automatic Story Generation — Consola unificada")
        while True:
            self.output(
                "\nMenú principal\n"
                "  1. Top-Down\n"
                "  2. Bottom-Up\n"
                "  3. Evaluar historia\n"
                "  0. Salir"
            )
            try:
                choice = self.input("> ").strip()
                if choice == "0":
                    self.output("Hasta luego.")
                    return 0
                if choice == "1":
                    self.top_down.run()
                elif choice == "2":
                    self.bottom_up.run()
                elif choice == "3":
                    self._evaluate_story()
                else:
                    self.output("Opción inválida.")
            except (EOFError, KeyboardInterrupt):
                self.output("\nOperación cancelada.")
                return 1
            except Exception as exc:
                self.output(f"Error: {exc}")

    def _evaluate_story(self) -> None:
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
        user = self.input("Usuario evaluador: ").strip()
        while not user:
            self.output("El usuario no puede estar vacío.")
            user = self.input("Usuario evaluador: ").strip()
        scores = {metric: self._score(metric) for metric in METRICS}
        destination = add_evaluation(stories[selected], user, scores)
        self.output(f"Evaluación guardada en: {destination}")

    def _story_choice(self, count: int) -> int | None:
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
        while True:
            value = self.input(f"{metric} [1-10]: ").strip()
            try:
                score = int(value)
            except ValueError:
                score = 0
            if 1 <= score <= 10:
                return score
            self.output("Introduce un entero entre 1 y 10.")


def main() -> int:
    return ConsoleApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
