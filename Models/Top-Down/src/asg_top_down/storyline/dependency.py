"""Deterministic world-state validation for factual plot candidates."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..domain import StorylineCast, WorldArtifact
from .models import PlotNodeProposal, StoryStateSnapshot


class DependencyIssue(BaseModel):
    code: str
    message: str


class DependencyReport(BaseModel):
    issues: list[DependencyIssue] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.issues


class DependencyValidator:
    """Validate references, predicates, movement, presence, and ownership."""

    def __init__(self, world: WorldArtifact, characters: StorylineCast) -> None:
        self.world = world
        self.characters = characters
        self.location_ids = {item.id for item in world.locations}
        self.character_ids = {item.id for item in characters.characters}
        self.object_ids = {item.id for item in world.objects}
        self.entity_kinds = {
            **dict.fromkeys(self.location_ids, "location"),
            **dict.fromkeys(self.character_ids, "character"),
            **dict.fromkeys(self.object_ids, "object"),
        }
        self.connections = {
            item.id: set(item.connected_location_ids) for item in world.locations
        }

    @staticmethod
    def _state(snapshot: StoryStateSnapshot) -> dict[str, object]:
        return {item.id: item for item in snapshot.entities}

    def validate(
        self,
        proposal: PlotNodeProposal,
        snapshot: StoryStateSnapshot,
        accepted_node_ids: set[str],
    ) -> DependencyReport:
        issues: list[DependencyIssue] = []
        entities = self._state(snapshot)

        if proposal.location_id not in self.location_ids:
            issues.append(DependencyIssue(
                code="UNKNOWN_LOCATION",
                message=f"event location is unknown: {proposal.location_id}",
            ))
        for ref in (proposal.subject, proposal.object):
            expected_kind = self.entity_kinds.get(ref.id)
            if ref.kind != "concept" and expected_kind is None:
                issues.append(DependencyIssue(
                    code="UNKNOWN_ENTITY", message=f"unknown {ref.kind}: {ref.id}",
                ))
            elif expected_kind and expected_kind != ref.kind:
                issues.append(DependencyIssue(
                    code="ENTITY_KIND_MISMATCH",
                    message=f"{ref.id} is {expected_kind}, not {ref.kind}",
                ))
            entity = entities.get(ref.id)
            if entity and ref.kind == "character":
                if entity.state.get("status", "alive") == "dead":
                    issues.append(DependencyIssue(
                        code="DEAD_CHARACTER", message=f"dead character acts: {ref.id}",
                    ))
                current = entity.state.get("location")
                if current and current != proposal.location_id:
                    issues.append(DependencyIssue(
                        code="CHARACTER_ABSENT",
                        message=f"{ref.id} is at {current}, not {proposal.location_id}",
                    ))
            if entity and ref.kind == "object":
                owner = entity.state.get("owner")
                location = entity.state.get("location")
                participant_ids = {proposal.subject.id, proposal.object.id}
                if owner and owner not in participant_ids:
                    issues.append(DependencyIssue(
                        code="OBJECT_UNAVAILABLE",
                        message=f"{ref.id} is owned by absent entity {owner}",
                    ))
                elif location and location != proposal.location_id and not owner:
                    issues.append(DependencyIssue(
                        code="OBJECT_ABSENT",
                        message=f"{ref.id} is at {location}, not {proposal.location_id}",
                    ))

        unknown_dependencies = set(proposal.depends_on_node_ids) - accepted_node_ids
        if unknown_dependencies:
            issues.append(DependencyIssue(
                code="UNKNOWN_DEPENDENCY",
                message=f"unknown causal dependencies: {sorted(unknown_dependencies)}",
            ))

        for predicate in proposal.preconditions:
            entity = entities.get(predicate.entity_id)
            if entity is None:
                issues.append(DependencyIssue(
                    code="FALSE_PRECONDITION",
                    message=f"precondition entity does not exist: {predicate.entity_id}",
                ))
                continue
            if predicate.attribute == "knowledge":
                actual = predicate.value in entity.knowledge
                if predicate.operator == "not_equals":
                    actual = not actual
            else:
                value = entity.state.get(predicate.attribute)
                actual = {
                    "equals": value == predicate.value,
                    "not_equals": value != predicate.value,
                    "contains": predicate.value is not None and predicate.value in (value or ""),
                    "exists": value is not None,
                }[predicate.operator]
            if not actual:
                issues.append(DependencyIssue(
                    code="FALSE_PRECONDITION",
                    message=(f"precondition failed for {predicate.entity_id}."
                             f"{predicate.attribute}"),
                ))

        seen_mutations: dict[tuple[str, str], str] = {}
        for mutation in proposal.effects:
            if mutation.entity_id not in entities and mutation.entity_id not in {
                proposal.subject.id, proposal.object.id,
            }:
                issues.append(DependencyIssue(
                    code="UNKNOWN_MUTATION_ENTITY",
                    message=f"effect references unknown entity: {mutation.entity_id}",
                ))
            key = (mutation.entity_id, mutation.attribute)
            previous = seen_mutations.get(key)
            if previous is not None and previous != mutation.value:
                issues.append(DependencyIssue(
                    code="CONTRADICTORY_EFFECTS",
                    message=f"conflicting effects for {mutation.entity_id}.{mutation.attribute}",
                ))
            seen_mutations[key] = mutation.value
            entity = entities.get(mutation.entity_id)
            if entity:
                unchanged = (
                    mutation.value in entity.knowledge
                    if mutation.attribute == "knowledge"
                    else entity.state.get(mutation.attribute) == mutation.value
                )
                if unchanged:
                    issues.append(DependencyIssue(
                        code="NO_OP_EFFECT",
                        message=f"effect does not change {mutation.entity_id}.{mutation.attribute}",
                    ))
            if mutation.attribute == "location":
                if mutation.value not in self.location_ids:
                    issues.append(DependencyIssue(
                        code="UNKNOWN_DESTINATION",
                        message=f"unknown destination: {mutation.value}",
                    ))
                current = entity.state.get("location") if entity else None
                allowed = self.connections.get(current, set()) if current else set()
                if current and mutation.value != current and mutation.value not in allowed:
                    issues.append(DependencyIssue(
                        code="ILLEGAL_MOVEMENT",
                        message=f"{mutation.entity_id} cannot move from {current} to {mutation.value}",
                    ))
            if mutation.attribute == "owner" and mutation.value not in self.character_ids:
                issues.append(DependencyIssue(
                    code="UNKNOWN_OWNER", message=f"unknown owner: {mutation.value}",
                ))
        return DependencyReport(issues=issues)
