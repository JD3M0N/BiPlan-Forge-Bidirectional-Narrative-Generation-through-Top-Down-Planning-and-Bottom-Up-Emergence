"""Política baseline de prioridades, sin dependencias externas."""

from __future__ import annotations

import random

from .contracts import Action, ActionType, Position
from .domain import CharacterState, WorldState
from .planning import bfs, neighbors


class PriorityPolicy:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def propose(self, agent: CharacterState, world: WorldState) -> Action:
        if agent.escaped:
            return self._action(agent, ActionType.WAIT, "escaped")

        # 1. Completar inmediatamente una operación disponible.
        inventory = set(agent.inventory)
        if {"battery", "flashlight"} <= inventory:
            agent.current_goal = "combine_flashlight"
            return self._action(
                agent, ActionType.COMBINE, "battery", secondary="flashlight"
            )

        component_owners = {
            item: obj.owner
            for item, obj in world.objects.items()
            if item in {"battery", "flashlight"} and obj.owner
        }
        if (
            len(component_owners) == 2
            and len(set(component_owners.values())) == 2
            and agent.id in component_owners.values()
        ):
            other_id = next(v for v in component_owners.values() if v != agent.id)
            other = world.characters[other_id]
            agent.current_goal = "meet_to_combine"
            if world.adjacent(agent.position, other.position):
                return self._action(
                    agent, ActionType.COMBINE, "battery", secondary="flashlight"
                )
            return self._move_toward(agent, world, other.position)

        if "working_flashlight" in inventory and "inspect_painting" not in world.solved:
            painting = self._known_feature(agent, world, "painting")
            if painting:
                agent.current_goal = "inspect_painting"
                if world.adjacent(agent.position, painting):
                    return self._action(agent, ActionType.INSPECT, "painting")
                return self._move_toward(agent, world, painting)

        if (
            "cabinet_code" in agent.beliefs.facts
            and "open_cabinet" not in world.solved
        ):
            cabinet = self._known_feature(agent, world, "cabinet")
            if cabinet:
                agent.current_goal = "open_cabinet"
                if world.adjacent(agent.position, cabinet):
                    return self._action(agent, ActionType.USE, "cabinet")
                return self._move_toward(agent, world, cabinet)

        if world.exit_unlocked:
            exit_position = world.feature("exit").position
            agent.current_goal = "escape"
            return self._move_toward(agent, world, exit_position)

        lever_obj = world.objects.get("lever")
        if lever_obj and lever_obj.owner == agent.id:
            lever = world.feature("lever").position
            agent.current_goal = "operate_lever"
            if world.adjacent(agent.position, lever):
                return self._action(agent, ActionType.USE, "lever")
            return self._move_toward(agent, world, lever)

        if "open_cabinet" in world.solved and lever_obj and lever_obj.owner is None:
            if world.adjacent(agent.position, lever_obj.position):  # type: ignore[arg-type]
                agent.current_goal = "get_lever"
                return self._action(agent, ActionType.PICK_UP, "lever")
            if "lever" in agent.beliefs.known_objects:
                return self._move_toward(
                    agent, world, agent.beliefs.known_objects["lever"]
                )

        if lever_obj and lever_obj.owner and lever_obj.owner != agent.id:
            helpers = sorted(i for i in world.characters if i != lever_obj.owner)
            if agent.id != helpers[0]:
                agent.current_goal = "stand_by"
                plate = world.feature("plate").position
                lever = world.feature("lever").position
                if agent.position in {plate, lever}:
                    free = [
                        p
                        for p in neighbors(agent.position)
                        if 0 <= p[0] < world.config.width
                        and 0 <= p[1] < world.config.height
                        and not world.blocked(p)
                        and p not in world.occupied()
                        and p not in {plate, lever}
                    ]
                    if free:
                        return self._action(
                            agent, ActionType.MOVE, sorted(free)[0]
                        )
                return self._action(
                    agent, ActionType.WAIT, "cooperation_assigned"
                )
            plate = world.feature("plate").position
            agent.current_goal = "hold_plate"
            if agent.position == plate:
                return self._action(agent, ActionType.HOLD, "plate")
            return self._move_toward(agent, world, plate, exact=True)

        # 2. Ir hacia componentes necesarios conocidos.
        if "assemble_flashlight" not in world.solved:
            for item in self._component_order(agent, world):
                obj = world.objects[item]
                if obj.owner is None and item in agent.beliefs.known_objects:
                    position = agent.beliefs.known_objects[item]
                    agent.current_goal = f"get_{item}"
                    if world.adjacent(agent.position, position):
                        return self._action(agent, ActionType.PICK_UP, item)
                    return self._move_toward(agent, world, position)

        # 3. Comunicar información nueva.
        snapshot = agent.beliefs.snapshot()
        if snapshot != agent.beliefs.shared_snapshot and len(world.characters) > 1:
            target = next(i for i in sorted(world.characters) if i != agent.id)
            agent.current_goal = "communicate"
            return self._action(
                agent,
                ActionType.COMMUNICATE,
                target,
                message="Comparto mis descubrimientos.",
            )

        # 4/5. Ayudar se materializa en las reglas anteriores; si no, explorar.
        agent.current_goal = "explore"
        frontier = {
            cell
            for cell in agent.beliefs.known_cells
            if cell not in agent.beliefs.known_walls
            and any(
                0 <= p[0] < world.config.width
                and 0 <= p[1] < world.config.height
                and p not in agent.beliefs.known_cells
                for p in neighbors(cell)
            )
        }
        if agent.position in frontier:
            return self._action(agent, ActionType.LOOK)
        if frontier:
            ordered = sorted(frontier)
            goal = ordered[self.rng.randrange(len(ordered))]
            return self._move_toward(agent, world, goal)
        return self._action(agent, ActionType.WAIT, "no_valid_action")

    def _component_order(
        self, agent: CharacterState, world: WorldState
    ) -> list[str]:
        ids = sorted(world.characters)
        preferred = "battery" if ids.index(agent.id) % 2 == 0 else "flashlight"
        return [preferred, "flashlight" if preferred == "battery" else "battery"]

    def _known_feature(
        self, agent: CharacterState, world: WorldState, kind: str
    ) -> Position | None:
        feature = world.feature(kind)
        return agent.beliefs.known_features.get(feature.id)

    def _move_toward(
        self,
        agent: CharacterState,
        world: WorldState,
        target: Position,
        *,
        exact: bool = False,
    ) -> Action:
        goals = {target}
        if not exact and target != world.feature("exit").position:
            goals |= {
                p
                for p in neighbors(target)
                if p in agent.beliefs.known_cells
                and p not in agent.beliefs.known_walls
            }
        possible_cells = {
            (x, y)
            for x in range(world.config.width)
            for y in range(world.config.height)
        }
        plan = bfs(
            agent.position,
            goals,
            possible_cells,
            agent.beliefs.known_walls
            | (world.occupied() - {agent.position} - goals),
        )
        if plan:
            if plan != agent.current_plan:
                agent.metrics.replans += 1
            agent.current_plan = plan
            return self._action(agent, ActionType.MOVE, plan[0])
        return self._action(agent, ActionType.LOOK)

    @staticmethod
    def _action(
        agent: CharacterState,
        kind: ActionType,
        target: str | Position | None = None,
        *,
        secondary: str | None = None,
        message: str | None = None,
    ) -> Action:
        return Action(
            actor_id=agent.id,
            kind=kind,
            target=target,
            secondary_target=secondary,
            message=message,
        )
