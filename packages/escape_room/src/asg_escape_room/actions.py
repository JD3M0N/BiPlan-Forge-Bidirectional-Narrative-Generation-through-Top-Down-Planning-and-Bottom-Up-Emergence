"""Deterministic action resolution for the Bottom-Up simulation."""

from __future__ import annotations

from collections.abc import Callable

from .contracts import Action, ActionType, ResolvedAction, RoomConfig
from .domain import CharacterState, ObjectState, WorldState
from .planning import neighbors

EventCallback = Callable[[str, list[str], str, dict | None], None]
PerceptionCallback = Callable[[CharacterState, int], dict]


class ActionResolver:
    """Resolve simultaneous proposals against a mutable world state."""

    def __init__(
        self,
        world: WorldState,
        config: RoomConfig,
        perceive: PerceptionCallback,
        emit_event: EventCallback,
    ) -> None:
        """Store the world and callbacks required to apply actions."""
        self.world = world
        self.config = config
        self.perceive = perceive
        self.emit_event = emit_event

    def resolve(self, proposals: dict[str, Action]) -> list[ResolvedAction]:
        """Resolve one simultaneous tick and return results sorted by actor."""
        order = self._rotating_order(proposals)
        results = self._resolve_moves(proposals, order)
        cooperative_pair = self._cooperative_pair(proposals)
        for actor_id in order:
            if actor_id in results:
                continue
            action = proposals[actor_id]
            valid, reason = self._execute_non_move(action, cooperative_pair)
            results[actor_id] = ResolvedAction(action=action, valid=valid, reason=reason)
        self._record_metrics(results)
        return [results[actor_id] for actor_id in sorted(results)]

    def _rotating_order(self, proposals: dict[str, Action]) -> list[str]:
        """Rotate actor priority each tick to avoid permanent ordering bias."""
        order = sorted(proposals)
        if order:
            shift = self.world.tick % len(order)
            order = order[shift:] + order[:shift]
        return order

    def _resolve_moves(
        self,
        proposals: dict[str, Action],
        order: list[str],
    ) -> dict[str, ResolvedAction]:
        """Resolve movement conflicts before applying other action types."""
        results: dict[str, ResolvedAction] = {}
        claimed: set[tuple[int, int]] = set()
        moving_from = {
            self.world.characters[actor_id].position
            for actor_id, action in proposals.items()
            if action.kind == ActionType.MOVE
        }
        for actor_id in order:
            action = proposals[actor_id]
            if action.kind != ActionType.MOVE:
                continue
            valid, reason = self._move(action, claimed, moving_from)
            results[actor_id] = ResolvedAction(action=action, valid=valid, reason=reason)
        return results

    def _move(
        self,
        action: Action,
        claimed: set[tuple[int, int]],
        moving_from: set[tuple[int, int]],
    ) -> tuple[bool, str]:
        """Validate and apply one movement proposal."""
        agent = self.world.characters[action.actor_id]
        target = action.target
        if not isinstance(target, tuple) or target not in neighbors(agent.position):
            return False, "destination_not_adjacent"
        if self.world.blocked(target):
            return False, "blocked"
        if target in claimed:
            return False, "movement_conflict"
        if target in self.world.occupied() and target not in moving_from:
            return False, "occupied"
        old = agent.position
        agent.position = target
        claimed.add(target)
        agent.metrics.distance += 1
        if target == self.world.feature("exit").position:
            agent.escaped = True
            self.emit_event("escaped", [agent.id], f"{agent.id} escapó.", None)
        else:
            self.emit_event(
                "move",
                [agent.id],
                f"{agent.id} se movió.",
                {"from": old, "to": target},
            )
        return True, ""

    def _cooperative_pair(
        self,
        proposals: dict[str, Action],
    ) -> tuple[Action, Action] | None:
        """Find a synchronized pressure-plate and lever action pair."""
        holds = [
            action
            for action in proposals.values()
            if action.kind == ActionType.HOLD and action.target == "plate"
        ]
        uses = [
            action
            for action in proposals.values()
            if action.kind == ActionType.USE and action.target == "lever"
        ]
        for hold in holds:
            for use in uses:
                if self._is_valid_pair(hold, use):
                    return hold, use
        return None

    def _is_valid_pair(self, hold: Action, use: Action) -> bool:
        """Check the positions and ownership required for cooperation."""
        if hold.actor_id == use.actor_id:
            return False
        holder = self.world.characters[hold.actor_id]
        user = self.world.characters[use.actor_id]
        return (
            holder.position == self.world.feature("plate").position
            and self.world.adjacent(user.position, self.world.feature("lever").position)
            and self.world.objects["lever"].owner == user.id
        )

    def _execute_non_move(
        self,
        action: Action,
        cooperative_pair: tuple[Action, Action] | None,
    ) -> tuple[bool, str]:
        """Dispatch a non-movement action to its focused handler."""
        agent = self.world.characters[action.actor_id]
        if action.kind == ActionType.LOOK:
            self.perceive(agent, self.config.perception_radius + 1)
            return True, ""
        if action.kind == ActionType.WAIT:
            return True, str(action.target or "")
        if action.kind == ActionType.PICK_UP and isinstance(action.target, str):
            return self._pick_up(agent, action.target)
        if action.kind == ActionType.DROP and isinstance(action.target, str):
            return self._drop(agent, action.target)
        if action.kind == ActionType.COMBINE:
            return self._combine(agent)
        if action.kind == ActionType.INSPECT and action.target == "painting":
            return self._inspect_painting(agent)
        if action.kind == ActionType.USE and action.target == "cabinet":
            return self._open_cabinet(agent)
        if action.kind in {ActionType.HOLD, ActionType.USE} and action.target in {
            "plate",
            "lever",
        }:
            return self._cooperate(action, cooperative_pair)
        if action.kind == ActionType.COMMUNICATE and isinstance(action.target, str):
            return self._communicate(agent, action.target)
        return False, "unsupported_action"

    def _pick_up(self, agent: CharacterState, object_id: str) -> tuple[bool, str]:
        """Pick up an available adjacent portable object."""
        obj = self.world.objects.get(object_id)
        if not obj or not obj.portable or obj.owner is not None or obj.position is None:
            return False, "object_unavailable"
        if not self.world.adjacent(agent.position, obj.position):
            return False, "object_not_near"
        obj.owner, obj.position = agent.id, None
        agent.inventory.append(obj.id)
        agent.beliefs.known_objects.pop(obj.id, None)
        agent.metrics.contributions += 1
        self.emit_event("pickup", [agent.id], f"{agent.id} recogió {obj.id}.", None)
        return True, ""

    def _drop(self, agent: CharacterState, object_id: str) -> tuple[bool, str]:
        """Drop an owned object at the actor's current position."""
        if object_id not in agent.inventory:
            return False, "item_not_owned"
        agent.inventory.remove(object_id)
        obj = self.world.objects[object_id]
        obj.owner, obj.position = None, agent.position
        return True, ""

    def _inspect_painting(self, agent: CharacterState) -> tuple[bool, str]:
        """Reveal the cabinet code when the painting prerequisites are met."""
        painting = self.world.feature("painting")
        if "working_flashlight" not in agent.inventory or not self.world.adjacent(
            agent.position,
            painting.position,
        ):
            return False, "puzzle_preconditions"
        if "inspect_painting" not in self.world.solved:
            self.world.solved.add("inspect_painting")
            agent.beliefs.facts.add("cabinet_code")
            agent.metrics.contributions += 1
            self.emit_event(
                "puzzle_solved",
                [agent.id],
                f"{agent.id} descubrió el código del armario.",
                {"puzzle": "inspect_painting"},
            )
        return True, ""

    def _open_cabinet(self, agent: CharacterState) -> tuple[bool, str]:
        """Open the cabinet and reveal the lever when its code is known."""
        cabinet = self.world.feature("cabinet")
        if "cabinet_code" not in agent.beliefs.facts or not self.world.adjacent(
            agent.position,
            cabinet.position,
        ):
            return False, "puzzle_preconditions"
        if "open_cabinet" not in self.world.solved:
            self.world.solved.add("open_cabinet")
            lever = self.world.objects["lever"]
            lever.position = cabinet.position
            agent.beliefs.known_objects["lever"] = cabinet.position
            agent.metrics.contributions += 1
            self.emit_event(
                "puzzle_solved",
                [agent.id],
                f"{agent.id} abrió el armario.",
                {"puzzle": "open_cabinet"},
            )
        return True, ""

    def _cooperate(
        self,
        action: Action,
        cooperative_pair: tuple[Action, Action] | None,
    ) -> tuple[bool, str]:
        """Apply a synchronized plate-and-lever solution once per tick."""
        if not cooperative_pair or action not in cooperative_pair:
            return False, "cooperation_not_synchronized"
        if self.world.exit_unlocked:
            return True, ""
        self.world.exit_unlocked = True
        self.world.solved.add("pressure_plate_and_lever")
        actors = [cooperative_pair[0].actor_id, cooperative_pair[1].actor_id]
        self._share_exit_map()
        for actor_id in actors:
            self.world.characters[actor_id].metrics.contributions += 1
        self.emit_event(
            "puzzle_solved",
            actors,
            "La placa y la palanca desbloquearon la salida.",
            {"puzzle": "pressure_plate_and_lever"},
        )
        return True, ""

    def _share_exit_map(self) -> None:
        """Reveal the full room and exit after the mechanism is activated."""
        all_cells = {(x, y) for x in range(self.config.width) for y in range(self.config.height)}
        exit_feature = self.world.feature("exit")
        for character in self.world.characters.values():
            character.beliefs.known_cells |= all_cells
            character.beliefs.known_walls |= set(self.config.walls)
            character.beliefs.known_features[exit_feature.id] = exit_feature.position

    def _communicate(self, agent: CharacterState, recipient_id: str) -> tuple[bool, str]:
        """Share the actor's complete knowledge with every other character."""
        other = self.world.characters.get(recipient_id)
        if not other or other.id == agent.id:
            return False, "invalid_recipient"
        for recipient in self.world.characters.values():
            if recipient.id == agent.id:
                continue
            recipient.beliefs.known_cells |= agent.beliefs.known_cells
            recipient.beliefs.known_walls |= agent.beliefs.known_walls
            recipient.beliefs.known_objects.update(agent.beliefs.known_objects)
            recipient.beliefs.known_features.update(agent.beliefs.known_features)
            recipient.beliefs.facts |= agent.beliefs.facts
        agent.beliefs.shared_snapshot = agent.beliefs.snapshot()
        agent.metrics.messages += 1
        self.emit_event(
            "communication",
            [agent.id, other.id],
            f"{agent.id} compartió sus descubrimientos con {other.id}.",
            None,
        )
        return True, ""

    def _combine(self, agent: CharacterState) -> tuple[bool, str]:
        """Combine flashlight components held by adjacent participants."""
        if "assemble_flashlight" in self.world.solved:
            return False, "puzzle_already_solved"
        owners = {item: self.world.objects[item].owner for item in ("battery", "flashlight")}
        actors = {owner for owner in owners.values() if owner}
        if not all(owners.values()):
            return False, "missing_component"
        if len(actors) == 2:
            other_id = next(actor_id for actor_id in actors if actor_id != agent.id)
            if not self.world.adjacent(
                agent.position,
                self.world.characters[other_id].position,
            ):
                return False, "components_not_together"
        if agent.id not in actors:
            return False, "actor_has_no_component"
        for item, owner in owners.items():
            self.world.characters[owner].inventory.remove(item)  # type: ignore[index]
            del self.world.objects[item]
        self.world.objects["working_flashlight"] = ObjectState(
            "working_flashlight",
            None,
            True,
            agent.id,
        )
        agent.inventory.append("working_flashlight")
        self.world.solved.add("assemble_flashlight")
        agent.metrics.contributions += 1
        self.emit_event(
            "puzzle_solved",
            sorted(actors),
            f"{agent.id} montó la linterna.",
            {"puzzle": "assemble_flashlight"},
        )
        return True, ""

    def _record_metrics(self, results: dict[str, ResolvedAction]) -> None:
        """Update per-character counters from resolved actions."""
        for actor_id, result in results.items():
            agent = self.world.characters[actor_id]
            agent.action_history.append(result.action.kind.value)
            if not result.valid:
                agent.metrics.invalid_actions += 1
            if result.action.kind == ActionType.WAIT:
                agent.metrics.waits += 1
