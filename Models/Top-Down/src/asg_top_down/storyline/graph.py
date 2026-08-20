"""In-memory factual state and relation graph for accepted narrative events."""

from __future__ import annotations

from typing import Protocol

from ..domain import StorylineCast, WorldArtifact
from .models import (
    EntityRelation, NarrativeEntity, NarrativeEntityGraphArtifact, PlotNode,
    StoryStateSnapshot,
)


class NarrativeGraphBackend(Protocol):
    def apply(self, node: PlotNode) -> None: ...
    def related(self, subject_id: str, object_id: str | None = None, limit: int = 10) -> StoryStateSnapshot: ...
    def artifact(self) -> NarrativeEntityGraphArtifact: ...
    def snapshot(self) -> StoryStateSnapshot: ...


class NarrativeEntityGraph:
    """Canonical entity state; rejected candidates never reach this graph."""

    def __init__(
        self,
        world: WorldArtifact | None = None,
        characters: StorylineCast | None = None,
    ) -> None:
        self._entities: dict[str, NarrativeEntity] = {}
        self._relations: list[EntityRelation] = []
        if world:
            for location in world.locations:
                self._entities[location.id] = NarrativeEntity(
                    id=location.id, name=location.name, kind="location",
                )
            for item in world.objects:
                state: dict[str, str] = {}
                if item.initial_location_id:
                    state["location"] = item.initial_location_id
                if item.initial_owner_character_id:
                    state["owner"] = item.initial_owner_character_id
                self._entities[item.id] = NarrativeEntity(
                    id=item.id, name=item.name, kind="object", state=state,
                )
        if characters:
            for character in characters.characters:
                state = {"status": character.initial_status}
                if character.initial_location_id:
                    state["location"] = character.initial_location_id
                self._entities[character.id] = NarrativeEntity(
                    id=character.id, name=character.name, kind="character",
                    state=state, knowledge=list(character.initial_knowledge),
                )
            for relation in characters.relationships:
                self._relations.append(EntityRelation(
                    source=relation.source_character_id,
                    verb=f"{relation.kind}:{relation.state}",
                    target=relation.target_character_id,
                    plot_node_id="initial-world-state", timestamp=0,
                ))

    def apply(self, node: PlotNode) -> None:
        for reference in (node.subject, node.object):
            self._entities.setdefault(reference.id, NarrativeEntity(
                id=reference.id, name=reference.name, kind=reference.kind,
            ))
        relation = EntityRelation(
            source=node.subject.id, verb=node.verb, target=node.object.id,
            plot_node_id=node.id, timestamp=node.timestamp,
        )
        if relation not in self._relations:
            self._relations.append(relation)
        for mutation in node.effects:
            entity = self._entities.setdefault(mutation.entity_id, NarrativeEntity(
                id=mutation.entity_id, name=mutation.entity_id, kind="concept",
            ))
            if mutation.attribute == "knowledge":
                if mutation.value not in entity.knowledge:
                    entity.knowledge.append(mutation.value)
            else:
                entity.state[mutation.attribute] = mutation.value
                if entity.kind == "object" and mutation.attribute == "owner":
                    entity.state.pop("location", None)
                elif entity.kind == "object" and mutation.attribute == "location":
                    entity.state.pop("owner", None)
            entity.last_event_id = node.id
        for entity_id in {node.subject.id, node.object.id}:
            self._entities[entity_id].last_event_id = node.id

    def related(
        self, subject_id: str, object_id: str | None = None, limit: int = 10,
    ) -> StoryStateSnapshot:
        ids = {subject_id}
        if object_id:
            ids.add(object_id)
        incident = [
            relation for relation in self._relations
            if relation.source in ids or relation.target in ids
        ]
        if object_id:
            directed = [
                relation for relation in incident
                if relation.source == subject_id and relation.target == object_id
            ]
            remainder = [relation for relation in incident if relation not in directed]
            relations = (
                sorted(directed, key=lambda item: item.timestamp, reverse=True)
                + sorted(remainder, key=lambda item: item.timestamp, reverse=True)
            )[:limit]
        else:
            relations = sorted(
                incident, key=lambda item: item.timestamp, reverse=True,
            )[:limit]
        related_ids = ids | {item.source for item in relations} | {item.target for item in relations}
        entities = [
            entity.model_copy(deep=True) for identifier, entity in self._entities.items()
            if identifier in related_ids
        ]
        return StoryStateSnapshot(entities=entities, relations=relations)

    def snapshot(self) -> StoryStateSnapshot:
        return StoryStateSnapshot(
            entities=[item.model_copy(deep=True) for item in self._entities.values()],
            relations=[item.model_copy(deep=True) for item in self._relations],
        )

    def artifact(self) -> NarrativeEntityGraphArtifact:
        snapshot = self.snapshot()
        return NarrativeEntityGraphArtifact(
            entities=snapshot.entities, relations=snapshot.relations,
        )
