"""Motor determinista de percepción, propuesta y resolución."""

from __future__ import annotations

import random
from collections import defaultdict

from .contracts import (
    Action,
    ActionType,
    Event,
    EventLog,
    ResolvedAction,
    RoomConfig,
    SimulationResult,
    TickRecord,
)
from .domain import CharacterState, WorldState
from .metrics import collect_metrics
from .planning import neighbors
from .policy import PriorityPolicy


class EscapeRoomModel:
    def __init__(self, config: RoomConfig, seed: int = 0) -> None:
        self.config = config
        self.seed = seed
        self.rng = random.Random(seed)
        self.world = WorldState(config)
        self.policy = PriorityPolicy(self.rng)
        self.event_log = EventLog()
        self.tick_records: list[TickRecord] = []
        self._perceive_all(config.perception_radius)

    def step(self) -> TickRecord:
        perceptions = self._perceive_all(self.config.perception_radius)
        proposals = {
            agent_id: self.policy.propose(agent, self.world)
            for agent_id, agent in sorted(self.world.characters.items())
        }
        resolutions = self.resolve_actions(proposals)
        record = TickRecord(
            tick=self.world.tick,
            perceptions=perceptions,
            proposals=proposals,
            resolutions=resolutions,
        )
        self.tick_records.append(record)
        self.world.tick += 1
        return record

    def _perceive_all(self, radius: int) -> dict[str, dict]:
        return {
            agent_id: self._perceive(agent, radius)
            for agent_id, agent in sorted(self.world.characters.items())
            if not agent.escaped
        }

    def _perceive(self, agent: CharacterState, radius: int) -> dict:
        visible: set[tuple[int, int]] = set()
        x, y = agent.position
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                point = (x + dx, y + dy)
                if (
                    abs(dx) + abs(dy) <= radius
                    and 0 <= point[0] < self.config.width
                    and 0 <= point[1] < self.config.height
                ):
                    visible.add(point)
        agent.beliefs.known_cells |= visible
        agent.beliefs.known_walls |= visible & self.config.walls
        for obj in self.world.objects.values():
            if (
                obj.position in visible
                and obj.owner is None
                and (obj.id != "lever" or "open_cabinet" in self.world.solved)
            ):
                agent.beliefs.known_objects[obj.id] = obj.position
        for feature in self.world.features.values():
            if feature.position in visible:
                agent.beliefs.known_features[feature.id] = feature.position
        return {
            "position": agent.position,
            "visible_cells": sorted(visible),
            "objects": dict(sorted(agent.beliefs.known_objects.items())),
            "features": dict(sorted(agent.beliefs.known_features.items())),
            "facts": sorted(agent.beliefs.facts),
        }

    def resolve_actions(self, proposals: dict[str, Action]) -> list[ResolvedAction]:
        results: dict[str, ResolvedAction] = {}
        order = sorted(proposals)
        if order:
            shift = self.world.tick % len(order)
            order = order[shift:] + order[:shift]

        # Los movimientos compiten por destino usando prioridad rotatoria.
        claimed: set[tuple[int, int]] = set()
        moving_from = {
            self.world.characters[i].position
            for i, a in proposals.items()
            if a.kind == ActionType.MOVE
        }
        for actor_id in order:
            action = proposals[actor_id]
            if action.kind != ActionType.MOVE:
                continue
            agent = self.world.characters[actor_id]
            target = action.target
            valid = isinstance(target, tuple) and target in neighbors(agent.position)
            reason = ""
            if not valid:
                reason = "destination_not_adjacent"
            elif self.world.blocked(target):
                valid, reason = False, "blocked"
            elif target in claimed:
                valid, reason = False, "movement_conflict"
            elif target in self.world.occupied() and target not in moving_from:
                valid, reason = False, "occupied"
            if valid:
                old = agent.position
                agent.position = target
                claimed.add(target)
                agent.metrics.distance += 1
                if target == self.world.feature("exit").position:
                    agent.escaped = True
                    self._event("escaped", [actor_id], f"{actor_id} escapó.")
                else:
                    self._event(
                        "move", [actor_id], f"{actor_id} se movió.", {"from": old, "to": target}
                    )
            results[actor_id] = self._resolved(action, valid, reason)

        # La cooperación se comprueba sobre el conjunto del tick.
        holds = [
            a
            for a in proposals.values()
            if a.kind == ActionType.HOLD and a.target == "plate"
        ]
        uses = [
            a
            for a in proposals.values()
            if a.kind == ActionType.USE and a.target == "lever"
        ]
        cooperative_pair: tuple[Action, Action] | None = None
        for hold in holds:
            for use in uses:
                if hold.actor_id != use.actor_id:
                    holder = self.world.characters[hold.actor_id]
                    user = self.world.characters[use.actor_id]
                    lever_owner = self.world.objects["lever"].owner
                    if (
                        holder.position == self.world.feature("plate").position
                        and self.world.adjacent(
                            user.position, self.world.feature("lever").position
                        )
                        and lever_owner == user.id
                    ):
                        cooperative_pair = (hold, use)
                        break

        for actor_id in order:
            if actor_id in results:
                continue
            action = proposals[actor_id]
            valid, reason = self._execute_non_move(action, cooperative_pair)
            results[actor_id] = self._resolved(action, valid, reason)

        for actor_id, result in results.items():
            agent = self.world.characters[actor_id]
            agent.action_history.append(result.action.kind.value)
            if not result.valid:
                agent.metrics.invalid_actions += 1
            if result.action.kind == ActionType.WAIT:
                agent.metrics.waits += 1
        return [results[i] for i in sorted(results)]

    def _execute_non_move(
        self, action: Action, cooperative_pair: tuple[Action, Action] | None
    ) -> tuple[bool, str]:
        agent = self.world.characters[action.actor_id]
        kind = action.kind
        if kind == ActionType.LOOK:
            self._perceive(agent, self.config.perception_radius + 1)
            return True, ""
        if kind == ActionType.WAIT:
            return True, str(action.target or "")
        if kind == ActionType.PICK_UP and isinstance(action.target, str):
            obj = self.world.objects.get(action.target)
            if not obj or not obj.portable or obj.owner is not None or obj.position is None:
                return False, "object_unavailable"
            if not self.world.adjacent(agent.position, obj.position):
                return False, "object_not_near"
            obj.owner, obj.position = agent.id, None
            agent.inventory.append(obj.id)
            agent.beliefs.known_objects.pop(obj.id, None)
            agent.metrics.contributions += 1
            self._event("pickup", [agent.id], f"{agent.id} recogió {obj.id}.")
            return True, ""
        if kind == ActionType.DROP and isinstance(action.target, str):
            if action.target not in agent.inventory:
                return False, "item_not_owned"
            agent.inventory.remove(action.target)
            obj = self.world.objects[action.target]
            obj.owner, obj.position = None, agent.position
            return True, ""
        if kind == ActionType.COMBINE:
            return self._combine(agent)
        if kind == ActionType.INSPECT and action.target == "painting":
            painting = self.world.feature("painting")
            if (
                "working_flashlight" not in agent.inventory
                or not self.world.adjacent(agent.position, painting.position)
            ):
                return False, "puzzle_preconditions"
            if "inspect_painting" not in self.world.solved:
                self.world.solved.add("inspect_painting")
                agent.beliefs.facts.add("cabinet_code")
                agent.metrics.contributions += 1
                self._event(
                    "puzzle_solved",
                    [agent.id],
                    f"{agent.id} descubrió el código del armario.",
                    {"puzzle": "inspect_painting"},
                )
            return True, ""
        if kind == ActionType.USE and action.target == "cabinet":
            cabinet = self.world.feature("cabinet")
            if (
                "cabinet_code" not in agent.beliefs.facts
                or not self.world.adjacent(agent.position, cabinet.position)
            ):
                return False, "puzzle_preconditions"
            if "open_cabinet" not in self.world.solved:
                self.world.solved.add("open_cabinet")
                lever = self.world.objects["lever"]
                lever.position = cabinet.position
                agent.beliefs.known_objects["lever"] = cabinet.position
                agent.metrics.contributions += 1
                self._event(
                    "puzzle_solved",
                    [agent.id],
                    f"{agent.id} abrió el armario.",
                    {"puzzle": "open_cabinet"},
                )
            return True, ""
        if kind in {ActionType.HOLD, ActionType.USE} and action.target in {
            "plate",
            "lever",
        }:
            if cooperative_pair and action in cooperative_pair:
                if not self.world.exit_unlocked:
                    self.world.exit_unlocked = True
                    self.world.solved.add("pressure_plate_and_lever")
                    actors = [cooperative_pair[0].actor_id, cooperative_pair[1].actor_id]
                    # El mecanismo hace un ruido evidente: todos conocen la salida y
                    # consolidan el mapa compartido para iniciar la evacuación.
                    all_cells = set().union(
                        *(a.beliefs.known_cells for a in self.world.characters.values())
                    )
                    all_walls = set().union(
                        *(a.beliefs.known_walls for a in self.world.characters.values())
                    )
                    exit_feature = self.world.feature("exit")
                    for character in self.world.characters.values():
                        character.beliefs.known_cells |= all_cells
                        character.beliefs.known_walls |= all_walls
                        character.beliefs.known_features[
                            exit_feature.id
                        ] = exit_feature.position
                    for actor in actors:
                        self.world.characters[actor].metrics.contributions += 1
                    self._event(
                        "puzzle_solved",
                        actors,
                        "La placa y la palanca desbloquearon la salida.",
                        {"puzzle": "pressure_plate_and_lever"},
                    )
                return True, ""
            return False, "cooperation_not_synchronized"
        if kind == ActionType.COMMUNICATE and isinstance(action.target, str):
            other = self.world.characters.get(action.target)
            if not other or other.id == agent.id:
                return False, "invalid_recipient"
            other.beliefs.known_cells |= agent.beliefs.known_cells
            other.beliefs.known_walls |= agent.beliefs.known_walls
            other.beliefs.known_objects.update(agent.beliefs.known_objects)
            other.beliefs.known_features.update(agent.beliefs.known_features)
            other.beliefs.facts |= agent.beliefs.facts
            agent.beliefs.shared_snapshot = agent.beliefs.snapshot()
            agent.metrics.messages += 1
            self._event(
                "communication",
                [agent.id, other.id],
                f"{agent.id} compartió sus descubrimientos con {other.id}.",
            )
            return True, ""
        return False, "unsupported_action"

    def _combine(self, agent: CharacterState) -> tuple[bool, str]:
        if "assemble_flashlight" in self.world.solved:
            return False, "puzzle_already_solved"
        owners = {item: self.world.objects[item].owner for item in ("battery", "flashlight")}
        actors = {owner for owner in owners.values() if owner}
        if not all(owners.values()):
            return False, "missing_component"
        if len(actors) == 2:
            other_id = next(i for i in actors if i != agent.id)
            if not self.world.adjacent(agent.position, self.world.characters[other_id].position):
                return False, "components_not_together"
        if agent.id not in actors:
            return False, "actor_has_no_component"
        for item, owner in owners.items():
            self.world.characters[owner].inventory.remove(item)  # type: ignore[index]
            del self.world.objects[item]
        from .domain import ObjectState

        self.world.objects["working_flashlight"] = ObjectState(
            "working_flashlight", None, True, agent.id
        )
        agent.inventory.append("working_flashlight")
        self.world.solved.add("assemble_flashlight")
        agent.metrics.contributions += 1
        self._event(
            "puzzle_solved",
            sorted(actors),
            f"{agent.id} montó la linterna.",
            {"puzzle": "assemble_flashlight"},
        )
        return True, ""

    def _resolved(self, action: Action, valid: bool, reason: str) -> ResolvedAction:
        return ResolvedAction(action=action, valid=valid, reason=reason)

    def _event(
        self, kind: str, actors: list[str], description: str, data: dict | None = None
    ) -> None:
        # Evita duplicar el evento cooperativo cuando se procesan sus dos acciones.
        if (
            kind == "puzzle_solved"
            and data
            and any(e.data.get("puzzle") == data.get("puzzle") for e in self.event_log.events)
        ):
            return
        self.event_log.events.append(
            Event(
                tick=self.world.tick,
                kind=kind,
                actor_ids=actors,
                description=description,
                data=data or {},
            )
        )

    def result(self) -> SimulationResult:
        success = all(a.escaped for a in self.world.characters.values())
        metrics = collect_metrics(self.world)
        return SimulationResult(
            seed=self.seed,
            success=success,
            reason="escaped" if success else "tick_limit",
            ticks=self.world.tick,
            solved_puzzles=sorted(self.world.solved),
            escaped_agents=sorted(
                a.id for a in self.world.characters.values() if a.escaped
            ),
            metrics=metrics,
        )


class SimulationRunner:
    def __init__(self, model: EscapeRoomModel, tick_limit: int = 300) -> None:
        self.model = model
        self.tick_limit = tick_limit

    def run(self) -> SimulationResult:
        while (
            self.model.world.tick < self.tick_limit
            and not all(a.escaped for a in self.model.world.characters.values())
        ):
            self.model.step()
        return self.model.result()


def run_simulation(
    room: RoomConfig, *, seed: int = 0, tick_limit: int = 300
) -> tuple[SimulationResult, EscapeRoomModel]:
    model = EscapeRoomModel(room, seed)
    return SimulationRunner(model, tick_limit).run(), model
