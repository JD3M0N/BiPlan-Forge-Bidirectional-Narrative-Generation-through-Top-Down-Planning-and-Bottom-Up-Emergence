"""Bucle interactivo de la simulación visual."""

from __future__ import annotations

from dataclasses import dataclass

from asg_escape_room.contracts import SimulationResult, TickRecord
from asg_escape_room.engine import EscapeRoomModel

from .renderer import ConsoleRenderer
from .terminal import (
    Clock,
    KeyboardInput,
    RealKeyboardInput,
    SystemClock,
    Terminal,
)


@dataclass(frozen=True)
class VisualOutcome:
    cancelled: bool
    result: SimulationResult | None
    model: EscapeRoomModel


class EscapeRoomVisualizer:
    def __init__(
        self,
        *,
        renderer: ConsoleRenderer | None = None,
        terminal: Terminal | None = None,
        keyboard: KeyboardInput | None = None,
        clock: Clock | None = None,
        interval: float = 1.5,
    ) -> None:
        self.renderer = renderer or ConsoleRenderer()
        self.terminal = terminal or Terminal()
        self.keyboard = keyboard or RealKeyboardInput()
        self.clock = clock or SystemClock()
        self.interval = max(0.1, min(5.0, interval))
        self.paused = False
        self.view_index = 0

    def run(
        self, model: EscapeRoomModel, *, tick_limit: int = 300
    ) -> VisualOutcome:
        last_record: TickRecord | None = None
        next_tick = self.clock.monotonic()
        self._draw(model, last_record)
        try:
            with self.keyboard:
                while (
                    model.world.tick < tick_limit
                    and not all(
                        agent.escaped
                        for agent in model.world.characters.values()
                    )
                ):
                    step_once = False
                    key = self.keyboard.poll()
                    if key:
                        normalized = key.lower()
                        if normalized == "q":
                            return VisualOutcome(True, None, model)
                        if key == " ":
                            self.paused = not self.paused
                        elif normalized == "n" and self.paused:
                            step_once = True
                        elif normalized in {"+", "="}:
                            self.interval = max(0.1, self.interval - 0.2)
                        elif normalized in {"-", "_"}:
                            self.interval = min(5.0, self.interval + 0.2)
                        elif normalized == "v":
                            self.view_index = (
                                self.view_index + 1
                            ) % len(self.renderer.views(model))
                        self._draw(model, last_record)
                    now = self.clock.monotonic()
                    if step_once or (not self.paused and now >= next_tick):
                        last_record = model.step()
                        next_tick = self.clock.monotonic() + self.interval
                        self._draw(model, last_record)
                    else:
                        self.clock.sleep(0.05)
        except KeyboardInterrupt:
            return VisualOutcome(True, None, model)
        return VisualOutcome(False, model.result(), model)

    def _draw(
        self, model: EscapeRoomModel, last_record: TickRecord | None
    ) -> None:
        views = self.renderer.views(model)
        view = views[self.view_index % len(views)]
        self.terminal.draw(
            self.renderer.render(
                model,
                view=view,
                paused=self.paused,
                interval=self.interval,
                last_record=last_record,
            )
        )

