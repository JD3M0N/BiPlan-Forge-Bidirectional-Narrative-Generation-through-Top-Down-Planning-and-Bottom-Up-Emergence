"""Deterministic perception and simulation lifecycle."""

from __future__ import annotations

import random

from .actions import ActionResolver
from .contracts import (
    Action,
    Event,
    EventLog,
    ResolvedAction,
    RoomConfig,
    SimulationResult,
    TickRecord,
)
from .domain import CharacterState, WorldState
from .metrics import collect_metrics
from .policy import PriorityPolicy


class EscapeRoomModel:
    """Coordinate perception, policy proposals, actions, and event history."""

    def __init__(self, config: RoomConfig, seed: int = 0) -> None:
        """Initialize deterministic world state from a validated room config."""
        self.config = config
        self.seed = seed
        self.rng = random.Random(seed)
        self.world = WorldState(config)
        self.policy = PriorityPolicy(self.rng)
        self.event_log = EventLog()
        self.tick_records: list[TickRecord] = []
        self.action_resolver = ActionResolver(
            self.world,
            self.config,
            self._perceive,
            self._event,
        )
        self._perceive_all(config.perception_radius)

    def step(self) -> TickRecord:
        """Advance perception, proposals, and resolution by one tick."""
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
        """Update and return perceptions for every active character."""
        return {
            agent_id: self._perceive(agent, radius)
            for agent_id, agent in sorted(self.world.characters.items())
            if not agent.escaped
        }

    def _perceive(self, agent: CharacterState, radius: int) -> dict:
        """Update one character's beliefs from visible nearby cells."""
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
        self._remember_visible_objects(agent, visible)
        self._remember_visible_features(agent, visible)
        return {
            "position": agent.position,
            "visible_cells": sorted(visible),
            "objects": dict(sorted(agent.beliefs.known_objects.items())),
            "features": dict(sorted(agent.beliefs.known_features.items())),
            "facts": sorted(agent.beliefs.facts),
        }

    def _remember_visible_objects(
        self,
        agent: CharacterState,
        visible: set[tuple[int, int]],
    ) -> None:
        """Add visible and currently available objects to character beliefs."""
        for obj in self.world.objects.values():
            if (
                obj.position in visible
                and obj.owner is None
                and (obj.id != "lever" or "open_cabinet" in self.world.solved)
            ):
                agent.beliefs.known_objects[obj.id] = obj.position

    def _remember_visible_features(
        self,
        agent: CharacterState,
        visible: set[tuple[int, int]],
    ) -> None:
        """Add visible room features to character beliefs."""
        for feature in self.world.features.values():
            if feature.position in visible:
                agent.beliefs.known_features[feature.id] = feature.position

    def resolve_actions(self, proposals: dict[str, Action]) -> list[ResolvedAction]:
        """Delegate simultaneous action resolution to the focused resolver."""
        return self.action_resolver.resolve(proposals)

    def _event(
        self,
        kind: str,
        actors: list[str],
        description: str,
        data: dict | None = None,
    ) -> None:
        """Append a unique simulation event to the chronological log."""
        if (
            kind == "puzzle_solved"
            and data
            and any(
                event.data.get("puzzle") == data.get("puzzle") for event in self.event_log.events
            )
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
        """Build the immutable result for the current simulation state."""
        success = all(agent.escaped for agent in self.world.characters.values())
        return SimulationResult(
            seed=self.seed,
            success=success,
            reason="escaped" if success else "tick_limit",
            ticks=self.world.tick,
            solved_puzzles=sorted(self.world.solved),
            escaped_agents=sorted(
                agent.id for agent in self.world.characters.values() if agent.escaped
            ),
            metrics=collect_metrics(self.world),
        )


class SimulationRunner:
    """Advance a model until every character escapes or time expires."""

    def __init__(self, model: EscapeRoomModel, tick_limit: int = 300) -> None:
        """Configure a model and its maximum number of ticks."""
        self.model = model
        self.tick_limit = tick_limit

    def run(self) -> SimulationResult:
        """Run the configured model to its deterministic terminal state."""
        while self.model.world.tick < self.tick_limit and not all(
            agent.escaped for agent in self.model.world.characters.values()
        ):
            self.model.step()
        return self.model.result()


def run_simulation(
    room: RoomConfig,
    *,
    seed: int = 0,
    tick_limit: int = 300,
) -> tuple[SimulationResult, EscapeRoomModel]:
    """Run one deterministic simulation and return its result and model."""
    model = EscapeRoomModel(room, seed)
    return SimulationRunner(model, tick_limit).run(), model
