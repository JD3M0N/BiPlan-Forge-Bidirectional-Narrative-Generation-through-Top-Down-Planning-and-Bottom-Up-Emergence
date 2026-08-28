"""Dependency-free priority policy for Bottom-Up characters."""

from __future__ import annotations

import random

from .contracts import Action, ActionType, Position
from .domain import CharacterState, WorldState
from .planning import bfs, neighbors


class PriorityPolicy:
    """Choose one deterministic, priority-ordered action per character."""

    def __init__(self, rng: random.Random) -> None:
        """Store the seeded random source used for frontier selection."""
        self.rng = rng

    def propose(self, agent: CharacterState, world: WorldState) -> Action:
        """Return the first applicable action from the policy priority list."""
        if agent.escaped:
            return self._action(agent, ActionType.WAIT, "escaped")
        decision_rules = (
            self._assemble_flashlight,
            self._advance_puzzles,
            self._escape,
            self._operate_owned_lever,
            self._collect_revealed_lever,
            self._support_lever_owner,
            self._collect_component,
            self._communicate,
        )
        for rule in decision_rules:
            action = rule(agent, world)
            if action is not None:
                return action
        return self._explore(agent, world)

    def _assemble_flashlight(
        self,
        agent: CharacterState,
        world: WorldState,
    ) -> Action | None:
        """Combine locally held components or move their owners together."""
        inventory = set(agent.inventory)
        if {"battery", "flashlight"} <= inventory:
            agent.current_goal = "combine_flashlight"
            return self._action(agent, ActionType.COMBINE, "battery", secondary="flashlight")
        component_owners = {
            item: obj.owner
            for item, obj in world.objects.items()
            if item in {"battery", "flashlight"} and obj.owner
        }
        if not (
            len(component_owners) == 2
            and len(set(component_owners.values())) == 2
            and agent.id in component_owners.values()
        ):
            return None
        other_id = next(owner for owner in component_owners.values() if owner != agent.id)
        other = world.characters[other_id]
        agent.current_goal = "meet_to_combine"
        if world.adjacent(agent.position, other.position):
            return self._action(agent, ActionType.COMBINE, "battery", secondary="flashlight")
        return self._move_toward(agent, world, other.position)

    def _advance_puzzles(
        self,
        agent: CharacterState,
        world: WorldState,
    ) -> Action | None:
        """Inspect the painting or open the cabinet when prerequisites exist."""
        if "working_flashlight" in agent.inventory and "inspect_painting" not in world.solved:
            painting = self._known_feature(agent, world, "painting")
            if painting:
                agent.current_goal = "inspect_painting"
                if world.adjacent(agent.position, painting):
                    return self._action(agent, ActionType.INSPECT, "painting")
                return self._move_toward(agent, world, painting)
        if "cabinet_code" in agent.beliefs.facts and "open_cabinet" not in world.solved:
            cabinet = self._known_feature(agent, world, "cabinet")
            if cabinet:
                agent.current_goal = "open_cabinet"
                if world.adjacent(agent.position, cabinet):
                    return self._action(agent, ActionType.USE, "cabinet")
                return self._move_toward(agent, world, cabinet)
        return None

    def _escape(self, agent: CharacterState, world: WorldState) -> Action | None:
        """Move toward the exit after the cooperative lock is released."""
        if not world.exit_unlocked:
            return None
        agent.current_goal = "escape"
        return self._move_toward(agent, world, world.feature("exit").position)

    def _operate_owned_lever(
        self,
        agent: CharacterState,
        world: WorldState,
    ) -> Action | None:
        """Carry an owned lever to its mechanism and operate it."""
        lever_obj = world.objects.get("lever")
        if not lever_obj or lever_obj.owner != agent.id:
            return None
        lever = world.feature("lever").position
        agent.current_goal = "operate_lever"
        if world.adjacent(agent.position, lever):
            return self._action(agent, ActionType.USE, "lever")
        return self._move_toward(agent, world, lever)

    def _collect_revealed_lever(
        self,
        agent: CharacterState,
        world: WorldState,
    ) -> Action | None:
        """Collect the lever after the cabinet has been opened."""
        lever_obj = world.objects.get("lever")
        if "open_cabinet" not in world.solved or not lever_obj or lever_obj.owner is not None:
            return None
        if world.adjacent(agent.position, lever_obj.position):  # type: ignore[arg-type]
            agent.current_goal = "get_lever"
            return self._action(agent, ActionType.PICK_UP, "lever")
        if "lever" in agent.beliefs.known_objects:
            return self._move_toward(agent, world, agent.beliefs.known_objects["lever"])
        return None

    def _support_lever_owner(
        self,
        agent: CharacterState,
        world: WorldState,
    ) -> Action | None:
        """Assign one helper to the plate while other characters stand clear."""
        lever_obj = world.objects.get("lever")
        if not lever_obj or not lever_obj.owner or lever_obj.owner == agent.id:
            return None
        helpers = sorted(actor_id for actor_id in world.characters if actor_id != lever_obj.owner)
        if agent.id != helpers[0]:
            return self._stand_clear(agent, world)
        plate = world.feature("plate").position
        agent.current_goal = "hold_plate"
        if agent.position == plate:
            return self._action(agent, ActionType.HOLD, "plate")
        return self._move_toward(agent, world, plate, exact=True)

    def _stand_clear(self, agent: CharacterState, world: WorldState) -> Action:
        """Keep unassigned helpers away from cooperative mechanism cells."""
        agent.current_goal = "stand_by"
        plate = world.feature("plate").position
        lever = world.feature("lever").position
        if agent.position in {plate, lever}:
            free = [
                point
                for point in neighbors(agent.position)
                if 0 <= point[0] < world.config.width
                and 0 <= point[1] < world.config.height
                and not world.blocked(point)
                and point not in world.occupied()
                and point not in {plate, lever}
            ]
            if free:
                return self._action(agent, ActionType.MOVE, sorted(free)[0])
        return self._action(agent, ActionType.WAIT, "cooperation_assigned")

    def _collect_component(
        self,
        agent: CharacterState,
        world: WorldState,
    ) -> Action | None:
        """Move toward and collect the preferred visible flashlight component."""
        if "assemble_flashlight" in world.solved:
            return None
        for item in self._component_order(agent, world):
            obj = world.objects[item]
            if obj.owner is not None or item not in agent.beliefs.known_objects:
                continue
            position = agent.beliefs.known_objects[item]
            agent.current_goal = f"get_{item}"
            if world.adjacent(agent.position, position):
                return self._action(agent, ActionType.PICK_UP, item)
            return self._move_toward(agent, world, position)
        return None

    def _communicate(self, agent: CharacterState, world: WorldState) -> Action | None:
        """Share newly discovered beliefs with another character."""
        snapshot = agent.beliefs.snapshot()
        if snapshot == agent.beliefs.shared_snapshot or len(world.characters) <= 1:
            return None
        target = next(actor_id for actor_id in sorted(world.characters) if actor_id != agent.id)
        agent.current_goal = "communicate"
        return self._action(
            agent,
            ActionType.COMMUNICATE,
            target,
            message="Comparto mis descubrimientos.",
        )

    def _explore(self, agent: CharacterState, world: WorldState) -> Action:
        """Inspect or move toward the boundary of currently known cells."""
        agent.current_goal = "explore"
        frontier = {
            cell
            for cell in agent.beliefs.known_cells
            if cell not in agent.beliefs.known_walls
            and any(
                0 <= point[0] < world.config.width
                and 0 <= point[1] < world.config.height
                and point not in agent.beliefs.known_cells
                for point in neighbors(cell)
            )
        }
        if agent.position in frontier:
            return self._action(agent, ActionType.LOOK)
        if frontier:
            ordered = sorted(frontier)
            goal = ordered[self.rng.randrange(len(ordered))]
            return self._move_toward(agent, world, goal)
        return self._action(agent, ActionType.WAIT, "no_valid_action")

    def _component_order(self, agent: CharacterState, world: WorldState) -> list[str]:
        """Assign alternating component preferences by stable actor order."""
        ids = sorted(world.characters)
        preferred = "battery" if ids.index(agent.id) % 2 == 0 else "flashlight"
        return [preferred, "flashlight" if preferred == "battery" else "battery"]

    def _known_feature(
        self,
        agent: CharacterState,
        world: WorldState,
        kind: str,
    ) -> Position | None:
        """Return a feature position only when the character has perceived it."""
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
        """Plan a shortest known path and return its next movement action."""
        goals = {target}
        if not exact and target != world.feature("exit").position:
            goals |= {
                point
                for point in neighbors(target)
                if point in agent.beliefs.known_cells and point not in agent.beliefs.known_walls
            }
        possible_cells = {
            (x, y) for x in range(world.config.width) for y in range(world.config.height)
        }
        plan = bfs(
            agent.position,
            goals,
            possible_cells,
            agent.beliefs.known_walls | (world.occupied() - {agent.position} - goals),
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
        """Build an action record for the current character."""
        return Action(
            actor_id=agent.id,
            kind=kind,
            target=target,
            secondary_target=secondary,
            message=message,
        )
