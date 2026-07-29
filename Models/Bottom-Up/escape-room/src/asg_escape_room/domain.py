"""Estado mutable del dominio, separado de contratos y políticas."""

from dataclasses import dataclass, field

from .contracts import AgentMetrics, Position, RoomConfig


@dataclass
class Beliefs:
    known_cells: set[Position] = field(default_factory=set)
    known_walls: set[Position] = field(default_factory=set)
    known_objects: dict[str, Position] = field(default_factory=dict)
    known_features: dict[str, Position] = field(default_factory=dict)
    facts: set[str] = field(default_factory=set)
    shared_snapshot: tuple = ()

    def snapshot(self) -> tuple:
        return (
            tuple(sorted(self.known_cells)),
            tuple(sorted(self.known_objects.items())),
            tuple(sorted(self.known_features.items())),
            tuple(sorted(self.facts)),
        )


@dataclass
class CharacterState:
    id: str
    position: Position
    role: str
    inventory: list[str] = field(default_factory=list)
    beliefs: Beliefs = field(default_factory=Beliefs)
    current_goal: str = "explore"
    current_plan: list[Position] = field(default_factory=list)
    escaped: bool = False
    action_history: list[str] = field(default_factory=list)
    metrics: AgentMetrics = field(default_factory=AgentMetrics)


@dataclass
class ObjectState:
    id: str
    position: Position | None
    portable: bool
    owner: str | None = None


class WorldState:
    def __init__(self, config: RoomConfig) -> None:
        self.config = config
        self.characters = {
            a.id: CharacterState(a.id, a.position, a.role) for a in config.agents
        }
        self.objects = {
            o.id: ObjectState(o.id, o.position, o.portable) for o in config.objects
        }
        self.features = {f.id: f for f in config.features}
        self.solved: set[str] = set()
        self.facts: set[str] = set()
        self.exit_unlocked = False
        self.tick = 0

    def feature(self, kind: str):
        return next(f for f in self.features.values() if f.kind == kind)

    def occupied(self) -> set[Position]:
        return {a.position for a in self.characters.values() if not a.escaped}

    def blocked(self, position: Position) -> bool:
        if position in self.config.walls:
            return True
        exit_feature = self.feature("exit")
        return position == exit_feature.position and not self.exit_unlocked

    def adjacent(self, left: Position, right: Position) -> bool:
        return abs(left[0] - right[0]) + abs(left[1] - right[1]) <= 1

