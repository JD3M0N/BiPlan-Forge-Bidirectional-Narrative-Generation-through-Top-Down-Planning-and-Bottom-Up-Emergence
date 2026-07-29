"""Contratos públicos y serializables de la simulación."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, model_validator

Position = tuple[int, int]


class ActionType(StrEnum):
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
    actor_id: str
    kind: ActionType
    target: str | Position | None = None
    secondary_target: str | None = None
    message: str | None = None


class ResolvedAction(BaseModel):
    action: Action
    valid: bool
    reason: str = ""


class ObjectConfig(BaseModel):
    id: str
    position: Position
    portable: bool = True


class FeatureConfig(BaseModel):
    id: str
    kind: Literal["painting", "cabinet", "plate", "lever", "exit"]
    position: Position
    locked: bool = False


class AgentConfig(BaseModel):
    id: str
    position: Position
    role: str = "explorer"


class PuzzleConfig(BaseModel):
    id: str
    requires: list[str] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    required_agents: int = Field(default=1, ge=1, le=3)


class RoomConfig(BaseModel):
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
    def validate_room(self) -> "RoomConfig":
        def inside(p: Position) -> bool:
            return 0 <= p[0] < self.width and 0 <= p[1] < self.height

        positions = [
            *(a.position for a in self.agents),
            *(o.position for o in self.objects),
            *(f.position for f in self.features),
            *self.walls,
        ]
        if any(not inside(p) for p in positions):
            raise ValueError("Todas las posiciones deben estar dentro del mapa")
        if any(a.position in self.walls for a in self.agents):
            raise ValueError("Un agente no puede comenzar dentro de una pared")
        ids = [a.id for a in self.agents] + [o.id for o in self.objects]
        ids += [f.id for f in self.features] + [p.id for p in self.puzzles]
        if len(ids) != len(set(ids)):
            raise ValueError("Los identificadores del mapa deben ser únicos")
        kinds = {f.kind for f in self.features}
        if not {"painting", "cabinet", "plate", "lever", "exit"} <= kinds:
            raise ValueError("Faltan elementos obligatorios del escape room")
        puzzle_ids = {p.id for p in self.puzzles}
        graph = {
            p.id: [req for req in p.requires if req in puzzle_ids] for p in self.puzzles
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
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
        known = set(ids) | {effect for p in self.puzzles for effect in p.effects}
        for puzzle in self.puzzles:
            missing = set(puzzle.requires) - known
            if missing:
                raise ValueError(
                    f"Referencias desconocidas en {puzzle.id}: {sorted(missing)}"
                )
        return self


class Event(BaseModel):
    tick: int
    kind: str
    actor_ids: list[str] = Field(default_factory=list)
    description: str
    data: dict[str, Any] = Field(default_factory=dict)


class TickRecord(BaseModel):
    tick: int
    perceptions: dict[str, dict[str, Any]]
    proposals: dict[str, Action]
    resolutions: list[ResolvedAction]


class EventLog(BaseModel):
    events: list[Event] = Field(default_factory=list)


class AgentMetrics(BaseModel):
    distance: int = 0
    messages: int = 0
    waits: int = 0
    invalid_actions: int = 0
    contributions: int = 0
    replans: int = 0


class SimulationMetrics(BaseModel):
    escaped: bool
    ticks: int
    puzzles_solved: int
    messages_sent: int
    blocked_time: int
    invalid_actions: int
    agents: dict[str, AgentMetrics]


class SimulationResult(BaseModel):
    seed: int
    success: bool
    reason: Literal["escaped", "tick_limit"]
    ticks: int
    solved_puzzles: list[str]
    escaped_agents: list[str]
    metrics: SimulationMetrics


class NarrativeProvider(Protocol):
    model_name: str

    def generate_text(self, *, system_instruction: str, prompt: str) -> str: ...

