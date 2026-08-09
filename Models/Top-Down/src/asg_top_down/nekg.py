"""Local, auditable narrative entity knowledge graph."""

import re
import unicodedata

from .schemas import EntityRelation, NarrativeEntity, NarrativeEntityGraphArtifact, PlotNode


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "entity"


class NarrativeEntityGraph:
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

    def related(self, subject: str, object_: str | None = None, limit: int = 10) -> list[EntityRelation]:
        source, target = _key(subject), _key(object_ or subject)
        matches = [r for r in self._relations if ({r.source, r.target} & {source, target})]
        if object_:
            exact = [r for r in matches if {r.source, r.target} == {source, target}]
            matches = exact + [r for r in matches if r not in exact]
        return sorted(matches, key=lambda r: r.timestamp, reverse=True)[:limit]

    def artifact(self) -> NarrativeEntityGraphArtifact:
        return NarrativeEntityGraphArtifact(entities=list(self._entities.values()), relations=self._relations)
