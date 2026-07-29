"""Renderizado puro del estado del escape room."""

from __future__ import annotations

from asg_escape_room.contracts import TickRecord
from asg_escape_room.engine import EscapeRoomModel


class ConsoleRenderer:
    FEATURE_SYMBOLS = {
        "painting": "P",
        "cabinet": "C",
        "plate": "=",
        "lever": "L",
        "exit": "E",
    }
    OBJECT_SYMBOLS = {
        "battery": "b",
        "flashlight": "f",
        "working_flashlight": "F",
        "lever": "l",
    }

    def views(self, model: EscapeRoomModel) -> list[str]:
        return ["WORLD", *sorted(model.world.characters)]

    def render(
        self,
        model: EscapeRoomModel,
        *,
        view: str = "WORLD",
        paused: bool = False,
        interval: float = 1.5,
        last_record: TickRecord | None = None,
    ) -> str:
        world = model.world
        selected = world.characters.get(view)
        known_cells = (
            selected.beliefs.known_cells if selected is not None else None
        )
        lines = [
            "ASG — Escape Room Visual",
            (
                f"Tick: {world.tick}  Seed: {model.seed}  "
                f"Velocidad: {interval:.1f}s  "
                f"Estado: {'PAUSA' if paused else 'EJECUTANDO'}  Vista: {view}"
            ),
            "",
        ]
        border = "+" + "--" * model.config.width + "+"
        lines.append(border)
        for y in range(model.config.height):
            row = ["|"]
            for x in range(model.config.width):
                position = (x, y)
                if known_cells is not None and position not in known_cells:
                    symbol = "?"
                else:
                    symbol = self._symbol(model, position, selected)
                row.append(f"{symbol} ")
            row.append("|")
            lines.append("".join(row))
        lines.append(border)
        lines.extend(["", "Agentes:"])
        for agent in world.characters.values():
            if selected is not None and agent.id != selected.id:
                continue
            last_action = agent.action_history[-1] if agent.action_history else "-"
            inventory = ", ".join(agent.inventory) or "vacío"
            lines.append(
                f"  {agent.id}: pos={agent.position} rol={agent.role} "
                f"objetivo={agent.current_goal} inventario=[{inventory}] "
                f"última={last_action} escapó={'sí' if agent.escaped else 'no'}"
            )
        solved = ", ".join(sorted(world.solved)) or "ninguno"
        lines.extend(
            [
                "",
                f"Acertijos resueltos: {solved}",
                f"Salida: {'DESBLOQUEADA' if world.exit_unlocked else 'bloqueada'}",
            ]
        )
        if last_record is not None:
            lines.extend(["", "Acciones del último tick:"])
            for resolution in last_record.resolutions:
                action = resolution.action
                status = "OK" if resolution.valid else f"INVÁLIDA: {resolution.reason}"
                target = f" → {action.target}" if action.target is not None else ""
                lines.append(
                    f"  {action.actor_id}: {action.kind.value}{target} [{status}]"
                )
        events = world.tick and model.event_log.events[-5:] or []
        lines.extend(["", "Eventos recientes:"])
        lines.extend(f"  t{event.tick}: {event.description}" for event in events)
        if not events:
            lines.append("  —")
        lines.extend(
            [
                "",
                "Leyenda: # pared, b batería, f linterna, P cuadro, C armario,",
                "         = placa, L palanca, E salida, ? desconocido, A/B/C agentes",
                "Controles: Espacio pausa | N paso | +/- velocidad | V vista | Q salir",
            ]
        )
        return "\n".join(lines)

    def _symbol(self, model, position, selected) -> str:
        world = model.world
        if position in model.config.walls:
            return "#"
        for agent in world.characters.values():
            if agent.escaped or agent.position != position:
                continue
            if selected is None or agent.id == selected.id:
                return agent.id[:1].upper()
        for obj in world.objects.values():
            if obj.position == position:
                if (
                    selected is None
                    or obj.id in selected.beliefs.known_objects
                ):
                    return self.OBJECT_SYMBOLS.get(obj.id, "o")
        for feature in world.features.values():
            if feature.position == position:
                if (
                    selected is None
                    or feature.id in selected.beliefs.known_features
                ):
                    if feature.kind == "exit" and world.exit_unlocked:
                        return "O"
                    return self.FEATURE_SYMBOLS[feature.kind]
        return "."

