"""Mutable domain state separated from contracts and policies."""

from dataclasses import dataclass, field

from .contracts import AgentMetrics, Position, RoomConfig


@dataclass
class Beliefs:
    """Represent Beliefs data and behavior."""

    known_cells: set[Position] = field(default_factory=set)
    known_walls: set[Position] = field(default_factory=set)
    known_objects: dict[str, Position] = field(default_factory=dict)
    known_features: dict[str, Position] = field(default_factory=dict)
    facts: set[str] = field(default_factory=set)
    shared_snapshot: tuple = ()

    def snapshot(self) -> tuple:
        """Handle the snapshot operation for Beliefs."""
        return (
            tuple(sorted(self.known_cells)),
            tuple(sorted(self.known_objects.items())),
            tuple(sorted(self.known_features.items())),
            tuple(sorted(self.facts)),
        )


@dataclass
class CharacterState:
    """Represent CharacterState data and behavior."""

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
    """Represent ObjectState data and behavior."""

    id: str
    position: Position | None
    portable: bool
    owner: str | None = None


class WorldState:
    """Represent WorldState data and behavior."""

    def __init__(self, config: RoomConfig) -> None:
        """Initialize the WorldState instance."""
        self.config = config
        self.characters = {a.id: CharacterState(a.id, a.position, a.role) for a in config.agents}
        self.objects = {o.id: ObjectState(o.id, o.position, o.portable) for o in config.objects}
        self.features = {f.id: f for f in config.features}
        self.solved: set[str] = set()
        self.facts: set[str] = set()
        self.exit_unlocked = False
        self.tick = 0

    def feature(self, kind: str):
        """Handle the feature operation for WorldState."""
        return next(f for f in self.features.values() if f.kind == kind)

    def occupied(self) -> set[Position]:
        """Handle the occupied operation for WorldState."""
        return {a.position for a in self.characters.values() if not a.escaped}

    def blocked(self, position: Position) -> bool:
        """Handle the blocked operation for WorldState."""
        if position in self.config.walls:
            return True
        exit_feature = self.feature("exit")
        return position == exit_feature.position and not self.exit_unlocked

    def adjacent(self, left: Position, right: Position) -> bool:
        """Handle the adjacent operation for WorldState."""
        return abs(left[0] - right[0]) + abs(left[1] - right[1]) <= 1
