"""Local, auditable narrative entity knowledge graph."""

import re
import unicodedata
from typing import Protocol

from .schemas import EntityRelation, EntityStateChange, NarrativeEntity, NarrativeEntityGraphArtifact, PlotNode


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "entity"


class NarrativeGraphBackend(Protocol):
    """Minimal backend boundary used by the incremental planner."""

    def apply(self, node: PlotNode, state_changes: list[EntityStateChange] | None = None) -> None: ...
    def related(self, subject: str, object_: str | None = None, limit: int = 10) -> list[EntityRelation]: ...
    def artifact(self) -> NarrativeEntityGraphArtifact: ...


class NarrativeEntityGraph:
    """In-memory backend with a JSON-serializable artifact representation."""
    def __init__(self) -> None:
        self._entities: dict[str, NarrativeEntity] = {}
        self._relations: list[EntityRelation] = []

    def add_node(self, node: PlotNode) -> None:
        source, target = _key(node.subject), _key(node.object)
        self._entities.setdefault(source, NarrativeEntity(id=source, name=node.subject))
        self._entities.setdefault(target, NarrativeEntity(id=target, name=node.object))
        relation = EntityRelation(source=source, verb=node.verb, target=target, plot_node_id=node.id, timestamp=node.timestamp)
        if relation not in self._relations:
            self._relations.append(relation)

    def apply(self, node: PlotNode, state_changes: list[EntityStateChange] | None = None) -> None:
        """Apply an accepted event immediately so it can ground the next CPN."""
        self.add_node(node)
        for change in state_changes or []:
            entity_id = _key(change.entity)
            entity = self._entities.setdefault(entity_id, NarrativeEntity(id=entity_id, name=change.entity))
            entity.state[change.attribute] = change.value
            entity.last_event_id = node.id
        for entity_id in {_key(node.subject), _key(node.object)}:
            self._entities[entity_id].last_event_id = node.id

    def related(self, subject: str, object_: str | None = None, limit: int = 10) -> list[EntityRelation]:
        source, target = _key(subject), _key(object_ or subject)
        incident = [relation for relation in self._relations
                    if relation.source in {source, target} or relation.target in {source, target}]
        if not object_:
            return sorted(incident, key=lambda relation: relation.timestamp, reverse=True)[:limit]

        directed = [relation for relation in incident
                    if relation.source == source and relation.target == target]
        remainder = [relation for relation in incident if relation not in directed]
        ordered = (
            sorted(directed, key=lambda relation: relation.timestamp, reverse=True)
            + sorted(remainder, key=lambda relation: relation.timestamp, reverse=True)
        )
        return ordered[:limit]

    @classmethod
    def from_artifact(cls, artifact: NarrativeEntityGraphArtifact) -> "NarrativeEntityGraph":
        backend = cls()
        backend._entities = {entity.id: entity.model_copy(deep=True) for entity in artifact.entities}
        backend._relations = [relation.model_copy(deep=True) for relation in artifact.relations]
        return backend

    def artifact(self) -> NarrativeEntityGraphArtifact:
        return NarrativeEntityGraphArtifact(entities=list(self._entities.values()), relations=self._relations)
