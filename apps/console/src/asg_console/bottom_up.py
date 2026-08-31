"""Interactive menus and persistence for Bottom-Up simulations."""

from __future__ import annotations

import argparse
import secrets
from collections.abc import Callable
from pathlib import Path

from asg_core import find_project_root
from asg_escape_room.cli import create_run_audio, room_with_agents, run_batch, run_one
from asg_escape_room.config import load_settings as load_bottom_up_settings
from asg_escape_room.engine import EscapeRoomModel
from asg_escape_room.narrative import GeminiNarrativeProvider, generate_story
from asg_escape_room.storage import RunRepository
from asg_evaluation import create_evaluation_template

from .types import InputFn, OutputFn
from .visualizer import EscapeRoomVisualizer


class BottomUpMenu:
    """Run normal, batch, or visual Bottom-Up simulations."""

    def __init__(
        self,
        input_fn: InputFn = input,
        output: OutputFn = print,
        visualizer_factory: Callable[..., EscapeRoomVisualizer] = EscapeRoomVisualizer,
    ) -> None:
        """Configure input, output, visualization, and the default room map."""
        self.input = input_fn
        self.output = output
        self.visualizer_factory = visualizer_factory
        root = find_project_root()
        self.default_map = root / "packages" / "escape_room" / "maps" / "escape_room.json"

    def run(self) -> None:
        """Display the Bottom-Up menu until the user returns."""
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
            actions = {"1": self._normal, "2": self._batch, "3": self._visual}
            action = actions.get(choice)
            if action:
                action()
            else:
                self.output("Opción inválida.")

    def _normal(self) -> None:
        """Run and persist one standard simulation."""
        output = run_one(self._simulation_options())
        self.output(f"Resultado guardado en: {output}")
        self._report_audio(output)

    def _batch(self) -> None:
        """Run and persist the fixed-size batch experiment."""
        args = argparse.Namespace(
            map=self._map(),
            seed=None,
            agents=2,
            tick_limit=self._integer("Límite de ticks [300]: ", default=300, minimum=1),
            batch=True,
            no_llm=True,
        )
        output = run_batch(args)
        self.output(f"Experimento guardado en: {output}")

    def _visual(self) -> None:
        """Run an interactive simulation and persist it unless cancelled."""
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
            model,
            tick_limit=args.tick_limit,
        )
        if outcome.cancelled:
            self.output("Visualización descartada; no se guardaron archivos.")
            return
        output = self._save_visual(args=args, seed=seed, room=room, model=outcome.model)
        result = outcome.result
        status = "escape exitoso" if result and result.success else "límite alcanzado"
        self.output(f"Simulación terminada: {status}.")
        self.output(f"Resultado guardado en: {output}")
        self._report_audio(output)
        self.input("Pulsa Enter para volver al menú...")

    def _save_visual(self, *, args, seed, room, model) -> Path:
        """Persist a completed visual simulation and its optional narrative."""
        settings = load_bottom_up_settings()
        repository = RunRepository(settings.output_root, room.name, settings.model)
        try:
            self._save_visual_configuration(repository, args, seed, room)
            result = model.result()
            repository.save_ticks(model.tick_records)
            repository.save_json("events.json", model.event_log)
            repository.save_json("result.json", result)
            repository.save_json("metrics.json", result.metrics)
            repository.complete_stage("simulation")
            provider = (
                GeminiNarrativeProvider(settings.api_key, settings.model)
                if not args.no_llm and settings.api_key
                else None
            )
            story, narrator, error = generate_story(result, model.event_log, provider)
            repository.save_text("story.md", story)
            create_evaluation_template(repository.run_dir)
            repository.complete_stage("narrative")
            create_run_audio(repository)
            repository.complete(narrator, error)
            return repository.run_dir
        except Exception as exc:
            repository.fail(str(exc))
            raise

    def _report_audio(self, output: Path) -> None:
        """Report whether narration was available for a completed story."""
        audio_path = output / "story.mp3"
        if audio_path.is_file():
            self.output(f"Audio disponible en: {audio_path}")
        else:
            self.output("La historia se guardó, pero no fue posible crear el audio.")

    @staticmethod
    def _save_visual_configuration(repository, args, seed, room) -> None:
        """Persist the reproducible inputs for a visual simulation."""
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

    def _simulation_options(self) -> argparse.Namespace:
        """Collect common options for normal and visual simulations."""
        map_path = self._map()
        agents = self._integer(
            "Número de agentes, 2 o 3 [2]: ",
            default=2,
            allowed={2, 3},
        )
        seed_text = self.input("Semilla reproducible [aleatoria]: ").strip()
        while seed_text and not self._is_integer(seed_text):
            self.output("Introduce un número entero o deja el campo vacío.")
            seed_text = self.input("Semilla reproducible [aleatoria]: ").strip()
        seed = int(seed_text) if seed_text else None
        tick_limit = self._integer("Límite de ticks [300]: ", default=300, minimum=1)
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
        """Prompt until an existing room-map path is selected."""
        value = self.input(f"Mapa [{self.default_map}]: ").strip()
        path = Path(value) if value else self.default_map
        while not path.is_file():
            self.output("El mapa indicado no existe.")
            value = self.input(f"Mapa [{self.default_map}]: ").strip()
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
        """Prompt until an integer satisfying the requested constraints is given."""
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
        """Prompt until a floating-point value falls within its bounds."""
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
            self.output(f"Introduce un número entre {minimum} y {maximum}.")

    def _yes_no(self, prompt: str, default: bool) -> bool:
        """Prompt until a localized yes-or-no answer is supplied."""
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
        """Return whether text can be parsed as an integer."""
        try:
            int(value)
            return True
        except ValueError:
            return False
