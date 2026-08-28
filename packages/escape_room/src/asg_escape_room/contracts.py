"""Public serializable contracts for the Bottom-Up simulation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, model_validator

Position = tuple[int, int]


def _validate_positions(room: RoomConfig) -> None:
    """Ensure every entity is inside the room and agents avoid walls."""
    positions = [
        *(agent.position for agent in room.agents),
        *(obj.position for obj in room.objects),
        *(feature.position for feature in room.features),
        *room.walls,
    ]
    if any(
        not (0 <= position[0] < room.width and 0 <= position[1] < room.height)
        for position in positions
    ):
        raise ValueError("Todas las posiciones deben estar dentro del mapa")
    if any(agent.position in room.walls for agent in room.agents):
        raise ValueError("Un agente no puede comenzar dentro de una pared")


def _room_identifiers(room: RoomConfig) -> list[str]:
    """Return all identifiers that must be unique within a room."""
    identifiers = [agent.id for agent in room.agents] + [obj.id for obj in room.objects]
    identifiers += [feature.id for feature in room.features]
    identifiers += [puzzle.id for puzzle in room.puzzles]
    return identifiers


def _validate_required_features(room: RoomConfig) -> None:
    """Require the feature types used by the deterministic puzzle engine."""
    kinds = {feature.kind for feature in room.features}
    if not {"painting", "cabinet", "plate", "lever", "exit"} <= kinds:
        raise ValueError("Faltan elementos obligatorios del escape room")


def _validate_puzzle_graph(room: RoomConfig) -> None:
    """Reject cycles among puzzle-to-puzzle requirements."""
    puzzle_ids = {puzzle.id for puzzle in room.puzzles}
    graph = {
        puzzle.id: [requirement for requirement in puzzle.requires if requirement in puzzle_ids]
        for puzzle in room.puzzles
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        """Visit one puzzle and reject a dependency back edge."""
        if node in visiting:
            raise ValueError("El grafo de acertijos contiene un ciclo")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for puzzle_id in graph:
        visit(puzzle_id)


def _validate_puzzle_references(room: RoomConfig, identifiers: list[str]) -> None:
    """Ensure every puzzle requirement references a known entity or effect."""
    known = set(identifiers) | {effect for puzzle in room.puzzles for effect in puzzle.effects}
    for puzzle in room.puzzles:
        missing = set(puzzle.requires) - known
        if missing:
            raise ValueError(f"Referencias desconocidas en {puzzle.id}: {sorted(missing)}")


class ActionType(StrEnum):
    """Represent ActionType data and behavior."""

    MOVE = "MOVE"
    LOOK = "LOOK"
    PICK_UP = "PICK_UP"
    DROP = "DROP"
    USE = "USE"
    COMBINE = "COMBINE"
    INSPECT = "INSPECT"
    COMMUNICATE = "COMMUNICATE"
    WAIT = "WAIT"
    HOLD = "HOLD"


class Action(BaseModel):
    """Represent Action data and behavior."""

    actor_id: str
    kind: ActionType
    target: str | Position | None = None
    secondary_target: str | None = None
    message: str | None = None


class ResolvedAction(BaseModel):
    """Represent ResolvedAction data and behavior."""

    action: Action
    valid: bool
    reason: str = ""


class ObjectConfig(BaseModel):
    """Represent ObjectConfig data and behavior."""

    id: str
    position: Position
    portable: bool = True


class FeatureConfig(BaseModel):
    """Represent FeatureConfig data and behavior."""

    id: str
    kind: Literal["painting", "cabinet", "plate", "lever", "exit"]
    position: Position
    locked: bool = False


class AgentConfig(BaseModel):
    """Represent AgentConfig data and behavior."""

    id: str
    position: Position
    role: str = "explorer"


class PuzzleConfig(BaseModel):
    """Represent PuzzleConfig data and behavior."""

    id: str
    requires: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    required_agents: int = Field(default=1, ge=1, le=3)


class RoomConfig(BaseModel):
    """Represent RoomConfig data and behavior."""

    name: str
    width: int = Field(ge=3)
    height: int = Field(ge=3)
    walls: set[Position] = Field(default_factory=set)
    agents: list[AgentConfig] = Field(min_length=2, max_length=3)
    objects: list[ObjectConfig]
    features: list[FeatureConfig]
    puzzles: list[PuzzleConfig]
    perception_radius: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def validate_room(self) -> RoomConfig:
        """Validate structural invariants required by the room engine."""
        _validate_positions(self)
        identifiers = _room_identifiers(self)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Los identificadores del mapa deben ser únicos")
        _validate_required_features(self)
        _validate_puzzle_graph(self)
        _validate_puzzle_references(self, identifiers)
        return self


class Event(BaseModel):
    """Represent Event data and behavior."""

    tick: int
    kind: str
    actor_ids: list[str] = Field(default_factory=list)
    description: str
    data: dict[str, Any] = Field(default_factory=dict)


class TickRecord(BaseModel):
    """Represent TickRecord data and behavior."""

    tick: int
    perceptions: dict[str, dict[str, Any]]
    proposals: dict[str, Action]
    resolutions: list[ResolvedAction]


class EventLog(BaseModel):
    """Represent EventLog data and behavior."""

    events: list[Event] = Field(default_factory=list)


class AgentMetrics(BaseModel):
    """Represent AgentMetrics data and behavior."""

    distance: int = 0
    messages: int = 0
    waits: int = 0
    invalid_actions: int = 0
    contributions: int = 0
    replans: int = 0


class SimulationMetrics(BaseModel):
    """Represent SimulationMetrics data and behavior."""

    escaped: bool
    ticks: int
    puzzles_solved: int
    messages_sent: int
    blocked_time: int
    invalid_actions: int
    agents: dict[str, AgentMetrics]


class SimulationResult(BaseModel):
    """Represent SimulationResult data and behavior."""

    seed: int
    success: bool
    reason: Literal["escaped", "tick_limit"]
    ticks: int
    solved_puzzles: list[str]
    escaped_agents: list[str]
    metrics: SimulationMetrics


class NarrativeProvider(Protocol):
    """Represent NarrativeProvider data and behavior."""

    model_name: str

    def generate_text(self, *, system_instruction: str, prompt: str) -> str:
        """Generate text."""
        ...
