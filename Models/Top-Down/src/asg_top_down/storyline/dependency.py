"""Deterministic world-state validation for factual plot candidates."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..domain import StorylineCast, TaxonomyApplication, WorldArtifact
from .models import ChapterAnchors, PlotNodeProposal, StoryStateSnapshot


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
                if predicate.attribute == "location" and value is None:
                    owner = entity.state.get("owner")
                    owner_entity = entities.get(owner) if owner else None
                    if owner_entity is not None:
                        value = owner_entity.state.get("location")
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


class CpnValidator:
    """Apply every deterministic CPN rule through one reusable entry point."""

    def __init__(self, world: WorldArtifact, characters: StorylineCast) -> None:
        self.dependencies = DependencyValidator(world, characters)

    @staticmethod
    def _issue(code: str, message: str) -> DependencyIssue:
        return DependencyIssue(code=code, message=message)

    @staticmethod
    def normalize_movement_origin(
        proposal: PlotNodeProposal, snapshot: StoryStateSnapshot,
    ) -> bool:
        """Place movement events at their source; return whether normalization occurred."""
        entities = {item.id: item for item in snapshot.entities}
        subject = entities.get(proposal.subject.id)
        current = subject.state.get("location") if subject else None
        destination = next((
            item.value for item in proposal.effects
            if item.entity_id == proposal.subject.id and item.attribute == "location"
        ), None)
        if current and destination == proposal.location_id and current != proposal.location_id:
            proposal.location_id = current
            return True
        return False

    @staticmethod
    def normalize_taxonomy_reference(
        proposal: PlotNodeProposal,
        taxonomy_application: TaxonomyApplication | None,
    ) -> bool:
        """Drop an invalid optional palette reference without rejecting a factual event."""
        if not taxonomy_application or not (
            proposal.taxonomy_id or proposal.taxonomy_movement_id
        ):
            return False
        selected = {
            (item.taxonomy_id, item.option_id)
            for item in taxonomy_application.selected_movements
        }
        reference = proposal.taxonomy_id, proposal.taxonomy_movement_id
        if None not in reference and reference in selected:
            return False
        proposal.taxonomy_id = None
        proposal.taxonomy_movement_id = None
        return True

    @staticmethod
    def cen_ready(
        proposal: PlotNodeProposal,
        snapshot: StoryStateSnapshot,
        anchor: ChapterAnchors,
    ) -> bool:
        """Return whether applying a CPN makes every factual CEN precondition true."""
        after = snapshot.model_copy(deep=True)
        entities = {item.id: item for item in after.entities}
        for mutation in proposal.effects:
            entity = entities.get(mutation.entity_id)
            if entity is None:
                continue
            if mutation.attribute == "knowledge":
                if mutation.value not in entity.knowledge:
                    entity.knowledge.append(mutation.value)
            else:
                entity.state[mutation.attribute] = mutation.value
                if entity.kind == "object" and mutation.attribute == "owner":
                    entity.state.pop("location", None)
                elif entity.kind == "object" and mutation.attribute == "location":
                    entity.state.pop("owner", None)

        for predicate in anchor.end_preconditions:
            entity = entities.get(predicate.entity_id)
            if entity is None:
                return False
            if predicate.attribute == "knowledge":
                present = predicate.value in entity.knowledge
                passed = not present if predicate.operator == "not_equals" else present
            else:
                value = entity.state.get(predicate.attribute)
                if predicate.attribute == "location" and value is None:
                    owner = entity.state.get("owner")
                    owner_entity = entities.get(owner) if owner else None
                    if owner_entity is not None:
                        value = owner_entity.state.get("location")
                passed = {
                    "equals": value == predicate.value,
                    "not_equals": value != predicate.value,
                    "contains": predicate.value is not None and predicate.value in (value or ""),
                    "exists": value is not None,
                }[predicate.operator]
                if (not passed and predicate.attribute == "location"
                        and entity.kind == "object"
                        and entity.state.get("owner") == anchor.end_subject.id):
                    owner_entity = entities.get(anchor.end_subject.id)
                    passed = bool(
                        owner_entity
                        and owner_entity.state.get("location") == anchor.end_location_id
                    )
            if not passed:
                return False

        subject = entities.get(anchor.end_subject.id)
        if subject and subject.kind == "character":
            subject_location = subject.state.get("location")
            subject_moves_there = any(
                item.entity_id == subject.id and item.attribute == "location"
                and item.value == anchor.end_location_id
                for item in anchor.end_effects
            )
            if subject_location != anchor.end_location_id and not subject_moves_there:
                return False
        object_entity = entities.get(anchor.end_object.id)
        epistemic_end = any(
            item.entity_id == anchor.end_subject.id and item.attribute == "knowledge"
            for item in anchor.end_effects
        )
        if object_entity and object_entity.kind == "object" and not epistemic_end:
            owner = object_entity.state.get("owner")
            location = object_entity.state.get("location")
            participants = {anchor.end_subject.id, anchor.end_object.id}
            if owner and owner not in participants:
                return False
            if location and location != anchor.end_location_id and not owner:
                return False
        return True

    def validate(
        self,
        proposal: PlotNodeProposal,
        snapshot: StoryStateSnapshot,
        accepted_node_ids: set[str],
        *,
        anchor: ChapterAnchors,
        forbidden_svos: set[tuple[str, str, str]],
        location_bridge: dict,
        taxonomy_application: TaxonomyApplication | None = None,
    ) -> DependencyReport:
        """Validate a proposal or reviewer replacement with the exact same rules."""
        issues = list(self.dependencies.validate(
            proposal, snapshot, accepted_node_ids,
        ).issues)

        reserved_effects = {
            (item.entity_id, item.attribute, item.value) for item in anchor.end_effects
        }
        for mutation in proposal.effects:
            if (mutation.entity_id, mutation.attribute, mutation.value) in reserved_effects:
                issues.append(self._issue(
                    "CEN_EFFECT_RESERVED",
                    "candidate performs an effect reserved for the chapter ending: "
                    f"{mutation.entity_id}.{mutation.attribute}",
                ))

        bridge_subject = location_bridge.get("subject_id")
        if location_bridge.get("reachable") is False:
            issues.append(self._issue(
                "UNREACHABLE_CEN_LOCATION",
                "the ending subject cannot reach the required CEN location through the world map",
            ))
        movement_destination = next((
            item.value for item in proposal.effects
            if item.entity_id == bridge_subject and item.attribute == "location"
        ), None)
        if (location_bridge.get("must_move_now")
                and movement_destination != location_bridge.get("required_next_location")):
            issues.append(self._issue(
                "REQUIRED_LOCATION_BRIDGE",
                "candidate must move the required CEN entity from "
                f"{location_bridge.get('current_location')} to adjacent "
                f"{location_bridge.get('required_next_location')} in this slot",
            ))

        if taxonomy_application and (proposal.taxonomy_id or proposal.taxonomy_movement_id):
            selected = {
                (item.taxonomy_id, item.option_id)
                for item in taxonomy_application.selected_movements
            }
            reference = proposal.taxonomy_id, proposal.taxonomy_movement_id
            if None in reference or reference not in selected:
                issues.append(self._issue(
                    "INVALID_TAXONOMY_REFERENCE",
                    "candidate taxonomy reference must identify one selected movement or be empty",
                ))

        signature = (
            proposal.subject.id, proposal.verb.casefold().strip(), proposal.object.id,
        )
        if signature in forbidden_svos:
            issues.append(self._issue(
                "DUPLICATE_SVO",
                "candidate repeats an anchor or accepted chapter event",
            ))
        return DependencyReport(issues=issues)
