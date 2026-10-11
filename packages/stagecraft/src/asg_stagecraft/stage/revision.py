"""Validate bounded revisions of scenes that have not been performed."""

from __future__ import annotations

from ..schemas import StoryPlan
from .schemas import FutureRevision, SceneBrief, StageFact


def materialize_revision(
    revision: FutureRevision,
    remaining: list[SceneBrief],
    plan: StoryPlan,
    achieved: set[str],
    facts: list[StageFact] | None = None,
) -> list[SceneBrief]:
    """Keep the original scene graph while accepting new outcomes and omitted events."""
    expected = [scene.scene_id for scene in remaining]
    actual = [scene.scene_id for scene in revision.scenes]
    if actual != expected:
        raise ValueError("revision must name each remaining scene once in original order")
    changed: list[SceneBrief] = []
    future_ids: set[str] = set()
    for original, proposal in zip(remaining, revision.scenes, strict=True):
        if not proposal.keep:
            if proposal.beats or proposal.objectives:
                raise ValueError("an omitted scene cannot carry beats or objectives")
            continue
        if not proposal.setting.strip() or not proposal.beats:
            raise ValueError("a kept scene needs a setting and at least one beat")
        old_ids = [beat.event_id for beat in original.beats]
        new_ids = [beat.event_id for beat in proposal.beats]
        if len(new_ids) != len(set(new_ids)) or new_ids != [
            item for item in old_ids if item in new_ids
        ]:
            raise ValueError("revised beats must be a nonempty ordered subset of original beats")
        cast = {member.character_id for member in original.cast}
        if not set(proposal.objectives) <= cast or not all(proposal.objectives.values()):
            raise ValueError("revised objectives must name only original cast members")
        objectives = {
            member.character_id: proposal.objectives.get(member.character_id, member.objective)
            for member in original.cast
        }
        by_id = {beat.event_id: beat for beat in original.beats}
        beats = [
            by_id[item.event_id].model_copy(
                update={
                    "outcome": item.outcome,
                    "purpose": item.purpose,
                    "conflict": item.conflict,
                    "promise_brief": "",
                    "dependencies": item.dependencies,
                    "supporting_fact_ids": item.supporting_fact_ids,
                }
            )
            for item in proposal.beats
        ]
        changed.append(
            original.model_copy(
                update={
                    "setting": proposal.setting,
                    "cast": [
                        member.model_copy(update={"objective": objectives[member.character_id]})
                        for member in original.cast
                    ],
                    "beats": beats,
                    "scripted_lines": [],
                }
            )
        )
        future_ids.update(new_ids)
    _validate_dependencies(revision, remaining, changed, plan, achieved, facts)
    return changed


def _validate_dependencies(revision, remaining, changed, plan, achieved, facts):
    """Require every prerequisite to precede its event and justify removed edges."""
    future_ids = {beat.event_id for scene in changed for beat in scene.beats}
    proposals = {
        beat.event_id: beat for scene in revision.scenes if scene.keep for beat in scene.beats
    }
    original_edges = {key: set() for key in future_ids}
    for dependency in plan.dependencies:
        if dependency.target_event_id in original_edges:
            original_edges[dependency.target_event_id].add(dependency.source_event_id)
    for scene in remaining:
        for beat in scene.beats:
            if beat.event_id in original_edges and beat.dependencies is not None:
                original_edges[beat.event_id] = set(beat.dependencies)
    supported = {
        fact.id
        for fact in facts or []
        if fact.status == "established" and fact.channel == "action" and fact.excerpt
    }
    order = [beat.event_id for scene in changed for beat in scene.beats]
    available = set(achieved)
    for key in order:
        proposal = proposals[key]
        edges = original_edges[key] if proposal.dependencies is None else set(proposal.dependencies)
        if original_edges[key] - edges and (
            not proposal.supporting_fact_ids or not set(proposal.supporting_fact_ids) <= supported
        ):
            raise ValueError("replacing a dependency requires cited established facts")
        if not set(proposal.supporting_fact_ids) <= supported:
            raise ValueError("revision cites an unknown or unestablished fact")
        if not edges <= available:
            raise ValueError("a kept event depends on an unperformed or omitted event")
        available.add(key)
