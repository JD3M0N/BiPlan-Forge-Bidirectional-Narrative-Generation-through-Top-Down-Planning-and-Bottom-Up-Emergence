"""Adaptive factual STORYTELLER planner for Top-Down 4.1."""

from __future__ import annotations

import json
import math
from collections import deque
from collections.abc import Callable

from pydantic import BaseModel, Field

from ..domain import (
    AgentStorySpec, ChapterPlan, StoryFrame, StorylineCast, StoryOutlineArtifact,
    StoryPlanArtifact, TaxonomyApplication, TaxonomyBrief, WorldArtifact,
)
from ..errors import StorylinePlanningError
from ..narrative_db import NarrativeBlueprint
from ..progress import PipelineEvent, PipelineEventCallback
from .cpn import CpnAttemptsExhausted, CpnContext, CpnPlanner
from .dependency import CpnValidator, DependencyValidator
from .graph import NarrativeEntityGraph, NarrativeGraphBackend
from .models import (
    AcceptedNodeRecord, ChapterAnchors, ChapterAnchorsArtifact, EntityRef,
    IncrementalStorylineArtifact, NarrativeEdge, NodeGoal, PlotNode, PlotNodeProposal,
    StateMutation,
)
from .reviewer import DramaticReviewer


class NodeReviewHistory(BaseModel):
    records: list[AcceptedNodeRecord] = Field(default_factory=list)
    rejected: list[dict] = Field(default_factory=list)


def chapter_word_budgets(request: AgentStorySpec) -> list[int]:
    """Return exact, balanced chapter budgets without delegating arithmetic to an LLM."""
    if request.requested_chapters:
        count = request.requested_chapters
        if request.target_words < count * 200:
            raise ValueError(
                "explicit chapter count requires at least 200 words per chapter"
            )
    else:
        count = max(1, math.ceil(request.target_words / 900))
    base, remainder = divmod(request.target_words, count)
    budgets = [base + (1 if index < remainder else 0) for index in range(count)]
    if not request.requested_chapters and request.target_words >= 400 and any(
        not 400 <= value <= 900 for value in budgets
    ):
        raise ValueError("automatic chapter budgets must remain between 400 and 900 words")
    return budgets


class StorylineState:
    def __init__(self, chapters: list[ChapterPlan]) -> None:
        self.chapters = chapters
        self.nodes: list[PlotNode] = []
        self.edges: list[NarrativeEdge] = []

    @staticmethod
    def _signature(node: PlotNode) -> tuple[str, str, str]:
        return node.subject.id, node.verb.casefold().strip(), node.object.id

    def accept(self, node: PlotNode, causal_links: list[NarrativeEdge]) -> None:
        known = {item.id for item in self.nodes}
        if node.id in known:
            raise ValueError(f"duplicate storyline node: {node.id}")
        repeated = [
            item for item in self.nodes if self._signature(item) == self._signature(node)
        ]
        repeated_cross_chapter_cbn = (
            node.node_type == "CBN"
            and repeated
            and all(item.chapter_id != node.chapter_id for item in repeated)
        )
        if repeated and not repeated_cross_chapter_cbn:
            raise ValueError("storyline event repeats an accepted SVO")
        dependencies = set(node.depends_on_node_ids)
        if dependencies - known:
            raise ValueError("node dependencies must reference accepted history")
        sources = {edge.source for edge in causal_links}
        if sources != dependencies or any(
            edge.target != node.id or edge.source not in known for edge in causal_links
        ):
            raise ValueError("causal links must exactly represent node dependencies")
        self.nodes.append(node)
        self.edges.extend(causal_links)
        self._topological_order()

    def recent(self, limit: int = 8) -> list[PlotNode]:
        return self.nodes[-limit:]

    def clone(self) -> "StorylineState":
        copy = StorylineState([item.model_copy(deep=True) for item in self.chapters])
        copy.nodes = [item.model_copy(deep=True) for item in self.nodes]
        copy.edges = [item.model_copy(deep=True) for item in self.edges]
        return copy

    def _topological_order(self) -> list[str]:
        ids = [item.id for item in self.nodes]
        incoming = dict.fromkeys(ids, 0)
        outgoing = {identifier: [] for identifier in ids}
        for edge in self.edges:
            if edge.source not in incoming or edge.target not in incoming:
                raise ValueError("storyline edge references an unknown node")
            incoming[edge.target] += 1
            outgoing[edge.source].append(edge.target)
        queue = [identifier for identifier in ids if incoming[identifier] == 0]
        order: list[str] = []
        while queue:
            identifier = queue.pop(0)
            order.append(identifier)
            for target in outgoing[identifier]:
                incoming[target] -= 1
                if incoming[target] == 0:
                    queue.append(target)
        if len(order) != len(ids):
            raise ValueError("storyline dependencies contain a cycle")
        return order

    def artifact(self) -> IncrementalStorylineArtifact:
        return IncrementalStorylineArtifact(
            chapters=self.chapters,
            nodes=self.nodes,
            accepted_edges=self.edges,
            topological_order=self._topological_order(),
        )


def _json(value) -> str:
    def convert(item):
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, dict):
            return {key: convert(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(child) for child in item]
        return item
    return json.dumps(convert(value), ensure_ascii=False, indent=2)


class IncrementalPlotPlanner:
    """Generate and review only factual plot events; story craft is downstream."""

    def __init__(
        self,
        provider,
        *,
        max_retries: int = 2,
        graph_factory: Callable[..., NarrativeGraphBackend] = NarrativeEntityGraph,
        on_event: PipelineEventCallback | None = None,
        on_attempt: Callable[[dict], None] | None = None,
        max_chapter_replans: int = 1,
    ) -> None:
        if max_retries < 0 or max_chapter_replans < 0:
            raise ValueError("retry counts cannot be negative")
        self.provider = provider
        self.max_retries = max_retries
        self.max_chapter_replans = max_chapter_replans
        self._graph_factory = graph_factory
        self.on_event = on_event
        self.on_attempt = on_attempt
        self.reviewer = DramaticReviewer(provider)
        self.nekg: NarrativeGraphBackend = graph_factory()
        self.history = NodeReviewHistory()
        self.state = StorylineState([])

    def _emit(self, kind: str, message: str, *, chapter_id: str | None = None,
              attempt: int | None = None) -> None:
        if self.on_event:
            self.on_event(PipelineEvent(
                kind=kind, message=message, stage="storyline",
                chapter_id=chapter_id, attempt=attempt,
            ))

    def _reject(self, record: dict) -> None:
        self.history.rejected.append(record)
        if self.on_attempt:
            self.on_attempt(record)
        issues = " | ".join(str(item) for item in record.get("issues", []))
        self._emit(
            "attempt_rejected",
            f"CPN {record['chapter_id']}:{record['slot']} intento "
            f"{record['attempt']} rechazado: {issues}",
            chapter_id=record.get("chapter_id"), attempt=record.get("attempt"),
        )

    def _checkpoint(self, callback) -> None:
        if callback:
            callback(self.state.artifact(), self.nekg.artifact(), self.history)

    def _effective_anchor_effects(self, effects, snapshot, subject, verb, object_ref,
                                  *, chapter_id: str, anchor_kind: str):
        entities = {item.id: item for item in snapshot.entities}
        effective = []
        for mutation in effects:
            entity = entities.get(mutation.entity_id)
            if entity is None:
                effective.append(mutation)
                continue
            unchanged = (
                mutation.value in entity.knowledge
                if mutation.attribute == "knowledge"
                else entity.state.get(mutation.attribute) == mutation.value
            )
            if not unchanged:
                effective.append(mutation)
        if len(effective) != len(effects):
            self._emit(
                "anchor_normalized",
                f"ancla {anchor_kind} de {chapter_id}: efectos redundantes eliminados",
                chapter_id=chapter_id,
            )
        if not effective:
            value = f"{subject.id} {verb.strip()} {object_ref.id}"
            current = entities.get(subject.id)
            if current and current.state.get("situation") == value:
                value = f"{value} ({anchor_kind})"
            effective = [StateMutation(
                entity_id=subject.id, attribute="situation", value=value,
            )]
        return effective

    def _normalize_epistemic_anchor_object(
        self, proposal: PlotNodeProposal, report, *, chapter_id: str, anchor_kind: str,
    ) -> bool:
        """Represent learning about an absent physical object as a factual concept."""
        epistemic_absence = (
            proposal.object.kind == "object"
            and any(
                item.entity_id == proposal.subject.id and item.attribute == "knowledge"
                for item in proposal.effects
            )
            and report.issues
            and {item.code for item in report.issues} <= {
                "OBJECT_ABSENT", "OBJECT_UNAVAILABLE",
            }
        )
        if not epistemic_absence:
            return False
        physical = proposal.object
        proposal.object = EntityRef(
            id=f"evidence-about-{physical.id}",
            name=f"evidence about {physical.name}",
            kind="concept",
        )
        self._emit(
            "anchor_normalized",
            f"{anchor_kind} epistemico de {chapter_id}: objeto ausente representado como concepto",
            chapter_id=chapter_id,
        )
        return True

    def _normalize_carried_cen_preconditions(
        self, anchor: ChapterAnchors, snapshot, *, chapter_id: str,
    ) -> None:
        """Replace stale object locations with ownership when the CEN actor carries them."""
        entities = {item.id: item for item in snapshot.entities}
        subject = entities.get(anchor.end_subject.id)
        if not subject or subject.state.get("location") != anchor.end_location_id:
            return
        for predicate in anchor.end_preconditions:
            entity = entities.get(predicate.entity_id)
            if (predicate.attribute == "location" and entity
                    and entity.kind == "object"
                    and entity.state.get("owner") == anchor.end_subject.id):
                predicate.attribute = "owner"
                predicate.operator = "equals"
                predicate.value = anchor.end_subject.id
                self._emit(
                    "anchor_normalized",
                    f"CEN de {chapter_id}: ubicacion de objeto portado convertida en propiedad",
                    chapter_id=chapter_id,
                )

    @staticmethod
    def _shortest_location_path(world: WorldArtifact, start: str, target: str) -> list[str]:
        connections = {item.id: item.connected_location_ids for item in world.locations}
        pending = deque([(start, [start])])
        visited = {start}
        while pending:
            current, path = pending.popleft()
            if current == target:
                return path
            for neighbor in connections.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append((neighbor, [*path, neighbor]))
        return []

    def _location_bridge(self, world: WorldArtifact, anchor, snapshot,
                         slot: int, maximum: int) -> dict:
        entities = {item.id: item for item in snapshot.entities}
        end_subject_location = next((
            item.value for item in anchor.end_preconditions
            if item.entity_id == anchor.end_subject.id
            and item.attribute == "location" and item.operator == "equals"
        ), None) or anchor.end_location_id
        targets = {anchor.end_subject.id: end_subject_location}
        for predicate in anchor.end_preconditions:
            entity = entities.get(predicate.entity_id)
            if (predicate.attribute == "location" and predicate.operator == "equals"
                    and entity is not None and entity.kind == "character"):
                targets[predicate.entity_id] = predicate.value
        end_object_ref = getattr(anchor, "end_object", None)
        end_object = entities.get(end_object_ref.id) if end_object_ref else None
        epistemic_end = any(
            item.entity_id == anchor.end_subject.id and item.attribute == "knowledge"
            for item in getattr(anchor, "end_effects", [])
        )
        if (end_object is not None and end_object.kind == "object" and not epistemic_end
                and not end_object.state.get("owner")):
            targets[end_object.id] = anchor.end_location_id

        requirements = []
        for subject_id, target in targets.items():
            subject = entities.get(subject_id)
            current = subject.state.get("location") if subject else None
            path = self._shortest_location_path(world, current, target) if current else []
            requirements.append({
                "subject_id": subject_id,
                "entity_kind": subject.kind if subject else None,
                "current_location": current,
                "target_location": target,
                "shortest_path": path,
                "steps": max(0, len(path) - 1),
                "reachable": current is None or current == target or bool(path),
            })

        pending = [item for item in requirements if item["steps"] > 0]
        primary = max(
            pending,
            key=lambda item: (item["steps"], item["entity_kind"] == "object"),
        ) if pending else requirements[0]
        remaining_slots = maximum - slot + 1
        must_move_now = bool(pending) and (
            primary["entity_kind"] == "object"
            or sum(item["steps"] for item in pending) >= remaining_slots
        )
        return {
            "subject_id": primary["subject_id"],
            "current_location": primary["current_location"],
            "pre_cen_location": primary["target_location"],
            "post_cen_location": anchor.end_location_id,
            "shortest_path": primary["shortest_path"],
            "reachable": all(item["reachable"] for item in requirements),
            "remaining_cpn_slots": remaining_slots,
            "must_move_now": must_move_now,
            "required_next_location": (
                primary["shortest_path"][1] if must_move_now else None
            ),
            "pending_character_movements": pending,
            "pending_entity_movements": pending,
        }

    def _normalize_movement_origin(self, proposal: PlotNodeProposal, snapshot,
                                   *, chapter_id: str) -> None:
        entities = {item.id: item for item in snapshot.entities}
        subject = entities.get(proposal.subject.id)
        current = subject.state.get("location") if subject else None
        destination = next((
            item.value for item in proposal.effects
            if item.entity_id == proposal.subject.id and item.attribute == "location"
        ), None)
        if current and destination == proposal.location_id and current != proposal.location_id:
            proposal.location_id = current
            self._emit(
                "movement_normalized",
                f"movimiento de {proposal.subject.id}: evento ubicado en origen {current}",
                chapter_id=chapter_id,
            )

    @staticmethod
    def _cen_reservation_issues(proposal: PlotNodeProposal, anchor) -> list[str]:
        issues: list[str] = []
        reserved_effects = {
            (item.entity_id, item.attribute, item.value) for item in anchor.end_effects
        }
        for mutation in proposal.effects:
            signature = mutation.entity_id, mutation.attribute, mutation.value
            if signature in reserved_effects:
                issues.append(
                    "candidate performs an effect reserved for the chapter ending: "
                    f"{mutation.entity_id}.{mutation.attribute}"
                )
        return issues

    def outline(
        self,
        request: AgentStorySpec,
        plan: StoryPlanArtifact,
        blueprint: NarrativeBlueprint,
        repair_feedback: str = "",
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> StoryOutlineArtifact:
        budgets = chapter_word_budgets(request)
        requested = (
            f"Create exactly {len(budgets)} chapters with these target_words values in order: "
            f"{budgets}. Do not choose a different chapter count or word allocation."
        )
        outline = self.provider.generate_structured(
            system_instruction=(
                "Create the high-level factual story frame before plot events. Produce a premise, "
                "complete synopsis, and ordered chapter titles and abstracts. Allocate exactly the "
                f"requested total words. {requested} Preserve the outer MICE thread: it opens first "
                "and closes last. Ensure causal escalation, a consequential climax, and enough "
                "aftermath. Internal planning text is English; chapter titles use the fiction language."
            ),
            prompt=(
                f"SPECIFICATION:\n{_json(request)}\n\nPLAN:\n{_json(plan)}"
                f"\n\nSTORY FRAME:\n{_json(plan.story_frame)}"
                f"\n\nRETRIEVED TAXONOMY:\n{_json(blueprint.model_context())}"
                f"\n\nSELECTED TAXONOMY:\n{_json(taxonomy_brief) if taxonomy_brief else 'none'}"
                f"{repair_feedback}"
            ),
            schema=StoryOutlineArtifact,
        )
        if len(outline.chapters) == len(budgets):
            for chapter, budget in zip(outline.chapters, budgets, strict=True):
                chapter.target_words = budget
        return outline

    def anchors(
        self,
        outline: StoryOutlineArtifact,
        world: WorldArtifact,
        characters: StorylineCast,
        story_frame: StoryFrame,
        repair_feedback: str = "",
    ) -> ChapterAnchorsArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Generate one concrete, distinct SVO begin event and end event for every chapter "
                "before internal events. Use canonical supplied entity and location IDs. Include "
                "typed observable state effects for both anchors and the factual preconditions of "
                "each ending. Adjacent chapters must connect smoothly. Do not duplicate an anchor "
                "inside a chapter. Return internal text in English."
            ),
            prompt=(
                f"OUTLINE:\n{_json(outline)}\n\nSTORY FRAME:\n{_json(story_frame)}"
                f"\n\nWORLD:\n{_json(world)}\n\nCHARACTERS:\n{_json(characters)}"
                f"{repair_feedback}"
            ),
            schema=ChapterAnchorsArtifact,
        )

    @staticmethod
    def min_cpn_count(chapter: ChapterPlan) -> int:
        return 1 if chapter.target_words < 400 else 2

    @staticmethod
    def max_cpn_count(chapter: ChapterPlan) -> int:
        return max(
            IncrementalPlotPlanner.min_cpn_count(chapter),
            min(8, math.ceil(chapter.target_words / 180)),
        )

    @staticmethod
    def _node(
        proposal: PlotNodeProposal,
        chapter: ChapterPlan,
        kind: str,
        global_order: int,
        local_order: int,
    ) -> PlotNode:
        return PlotNode(
            id=f"n_{global_order:04d}", chapter_id=chapter.id, node_type=kind,
            location_id=proposal.location_id,
            subject=proposal.subject, verb=proposal.verb, object=proposal.object,
            timestamp=global_order - 1, global_order=global_order,
            local_order=local_order, target_words=1,
            depends_on_node_ids=proposal.depends_on_node_ids,
            preconditions=proposal.preconditions, effects=proposal.effects,
            intention=proposal.intention, conflict=proposal.conflict,
            consequence=proposal.consequence,
            goals=[NodeGoal(
                purpose=proposal.purpose,
                narrative_function=proposal.narrative_function,
                taxonomy_id=proposal.taxonomy_id,
                taxonomy_movement_id=proposal.taxonomy_movement_id,
                success_criteria=["The event produces its declared observable mutations"],
            )],
        )

    @staticmethod
    def _links(node: PlotNode) -> list[NarrativeEdge]:
        return [NarrativeEdge(
            source=source, target=node.id,
            relation="causes", strength=5,
            rationale=f"Accepted event {source} is an explicit factual dependency",
        ) for source in node.depends_on_node_ids]

    def _graph_from_state(
        self, world: WorldArtifact, characters: StorylineCast, state: StorylineState,
    ) -> NarrativeGraphBackend:
        graph = self._graph_factory(world, characters)
        for node in state.nodes:
            graph.apply(node)
        return graph

    def _replacement_anchor(
        self,
        chapter: ChapterPlan,
        outline: StoryOutlineArtifact,
        current: ChapterAnchors,
        world: WorldArtifact,
        characters: StorylineCast,
        story_frame: StoryFrame,
        failures: list[dict],
    ) -> ChapterAnchors:
        """Regenerate only the failed chapter's anchors from compact failure evidence."""
        digest = [
            {
                "slot": item.get("slot"),
                "stage": item.get("stage"),
                "issue_codes": item.get("issue_codes", []),
                "issues": item.get("issues", []),
            }
            for item in failures[-8:]
        ]
        self._emit(
            "agent_called", "se llamo al agente chapter_anchor_replanner",
            chapter_id=chapter.id,
        )
        replacement = self.provider.generate_structured(
            system_instruction=(
                "Replace the begin and end anchors for exactly one failed chapter. Return one anchor "
                "entry with the same chapter_id. Use canonical entity and location IDs. The begin "
                "must be valid in CURRENT COMMITTED STATE. The end must be reachable through adjacent "
                "locations within the chapter's CPN limit, must differ from the begin SVO, and must "
                "declare factual preconditions that internal CPNs can establish. Do not solve the end "
                "event inside the begin anchor. Return internal text in English."
            ),
            prompt=(
                f"CHAPTER:\n{_json(chapter)}\n\nOUTLINE CONTEXT:\n{_json(outline.chapters)}"
                f"\n\nSTORY FRAME:\n{_json(story_frame)}"
                f"\n\nWORLD:\n{_json(world)}\n\nCHARACTERS:\n{_json(characters)}"
                f"\n\nCURRENT COMMITTED STATE:\n{_json(self.nekg.snapshot())}"
                f"\n\nFAILED ANCHORS:\n{_json(current)}"
                f"\n\nCPN FAILURE DIGEST:\n{_json(digest)}"
                f"\n\nCPN LIMIT: {self.max_cpn_count(chapter)}"
            ),
            schema=ChapterAnchorsArtifact,
        )
        if len(replacement.anchors) != 1 or replacement.anchors[0].chapter_id != chapter.id:
            raise StorylinePlanningError(
                f"Gemini no devolvio un reemplazo unico para las anclas de {chapter.id}.",
                details={
                    "chapter_id": chapter.id,
                    "returned_chapter_ids": [item.chapter_id for item in replacement.anchors],
                },
            )
        return replacement.anchors[0]

    @staticmethod
    def _allocate_words(chapter: ChapterPlan, nodes: list[PlotNode]) -> None:
        begin, *middle, end = nodes
        begin.target_words = max(1, round(chapter.target_words * .15))
        end.target_words = max(1, round(chapter.target_words * .15))
        remaining = chapter.target_words - begin.target_words - end.target_words
        base, remainder = divmod(remaining, len(middle))
        for index, node in enumerate(middle):
            node.target_words = max(1, base + (1 if index < remainder else 0))
        difference = chapter.target_words - sum(item.target_words for item in nodes)
        middle[-1].target_words += difference

    def _cpn_context(
        self, chapter: ChapterPlan, anchor: ChapterAnchors, world: WorldArtifact,
        characters: StorylineCast, story_frame: StoryFrame,
        chapter_cpns: list[PlotNode], slot: int, minimum: int, maximum: int,
        taxonomy_brief: TaxonomyBrief | None,
        taxonomy_application: TaxonomyApplication | None,
    ) -> CpnContext:
        snapshot = self.nekg.snapshot()
        forbidden = {
            (anchor.begin_subject.id, anchor.begin_verb.casefold().strip(), anchor.begin_object.id),
            (anchor.end_subject.id, anchor.end_verb.casefold().strip(), anchor.end_object.id),
            *((item.subject.id, item.verb.casefold().strip(), item.object.id) for item in chapter_cpns),
            *((item.subject.id, item.verb.casefold().strip(), item.object.id)
              for item in self.state.nodes if item.chapter_id == chapter.id),
        }
        return CpnContext(
            chapter=chapter, anchor=anchor, world=world, characters=characters,
            story_frame=story_frame, chapter_cpns=tuple(chapter_cpns),
            recent_nodes=tuple(self.state.recent(8)), snapshot=snapshot,
            accepted_node_ids=frozenset(item.id for item in self.state.nodes),
            forbidden_svos=frozenset(forbidden),
            location_bridge=self._location_bridge(world, anchor, snapshot, slot, maximum),
            slot=slot, minimum=minimum, maximum=maximum,
            taxonomy_brief=taxonomy_brief,
            taxonomy_application=taxonomy_application,
        )

    def _plan_chapter(
        self, chapter: ChapterPlan, anchor: ChapterAnchors, world: WorldArtifact,
        characters: StorylineCast, story_frame: StoryFrame, cpn_planner: CpnPlanner,
        validator: DependencyValidator, on_checkpoint,
        taxonomy_brief: TaxonomyBrief | None,
        taxonomy_application: TaxonomyApplication | None, *, attempt_offset: int,
    ) -> None:
        global_order = len(self.state.nodes) + 1
        previous = self.state.nodes[-1] if self.state.nodes else None
        before_begin = self.nekg.snapshot()
        begin_effects = self._effective_anchor_effects(
            anchor.begin_effects, before_begin, anchor.begin_subject, anchor.begin_verb,
            anchor.begin_object, chapter_id=chapter.id, anchor_kind="CBN",
        )
        begin_proposal = PlotNodeProposal(
            location_id=anchor.begin_location_id, subject=anchor.begin_subject,
            verb=anchor.begin_verb, object=anchor.begin_object,
            purpose="Establish the chapter's factual initial state",
            narrative_function="chapter_begin",
            depends_on_node_ids=[] if previous is None else [previous.id],
            effects=begin_effects, intention="Continue the active character goal",
            conflict="The central opposition remains active",
            consequence="The chapter's initial conditions become unavoidable",
        )
        begin_report = validator.validate(
            begin_proposal, before_begin, {item.id for item in self.state.nodes},
        )
        if self._normalize_epistemic_anchor_object(
            begin_proposal, begin_report, chapter_id=chapter.id, anchor_kind="CBN",
        ):
            begin_report = validator.validate(
                begin_proposal, before_begin, {item.id for item in self.state.nodes},
            )
        if not begin_report.passed:
            raise StorylinePlanningError(
                f"El CBN de {chapter.id} contradice el estado del mundo.",
                details={"issues": [item.model_dump() for item in begin_report.issues]},
            )
        begin = self._node(begin_proposal, chapter, "CBN", global_order, 1)
        self.state.accept(begin, self._links(begin))
        self.nekg.apply(begin)
        global_order += 1
        self._checkpoint(on_checkpoint)

        chapter_cpns: list[PlotNode] = []
        minimum, maximum = self.min_cpn_count(chapter), self.max_cpn_count(chapter)
        aligned = False
        for slot in range(1, maximum + 1):
            context = self._cpn_context(
                chapter, anchor, world, characters, story_frame, chapter_cpns,
                slot, minimum, maximum, taxonomy_brief, taxonomy_application,
            )
            result = cpn_planner.plan_slot(
                context, self.nekg, attempt_offset=attempt_offset,
            )
            candidate, review = result.candidate, result.review
            if candidate is None or review is None:
                raise RuntimeError("accepted CPN result is incomplete")
            node = self._node(candidate, chapter, "CPN", global_order, slot + 1)
            self.state.accept(node, self._links(node))
            self.nekg.apply(node)
            self.history.records.append(AcceptedNodeRecord(
                node=node, review=review, attempt=result.attempt,
            ))
            chapter_cpns.append(node)
            global_order += 1
            aligned = review.aligns_with_cen and len(chapter_cpns) >= minimum
            self._checkpoint(on_checkpoint)
            if aligned:
                break
        if not aligned:
            raise StorylinePlanningError(
                f"El capitulo {chapter.id} no conecto con su CEN dentro del limite.",
                details={"chapter_id": chapter.id, "max_cpn": maximum},
            )

        before_end = self.nekg.snapshot()
        self._normalize_carried_cen_preconditions(
            anchor, before_end, chapter_id=chapter.id,
        )
        end_effects = self._effective_anchor_effects(
            anchor.end_effects, before_end, anchor.end_subject, anchor.end_verb,
            anchor.end_object, chapter_id=chapter.id, anchor_kind="CEN",
        )
        end_proposal = PlotNodeProposal(
            location_id=anchor.end_location_id, subject=anchor.end_subject,
            verb=anchor.end_verb, object=anchor.end_object,
            purpose="Establish the chapter's factual end state",
            narrative_function="chapter_end", depends_on_node_ids=[chapter_cpns[-1].id],
            preconditions=anchor.end_preconditions, effects=end_effects,
            intention="Resolve or transform the active chapter goal",
            conflict="The outcome has a meaningful cost",
            consequence="The chapter ending changes the next chapter's conditions",
        )
        self._normalize_movement_origin(end_proposal, before_end, chapter_id=chapter.id)
        end_report = validator.validate(
            end_proposal, before_end, {item.id for item in self.state.nodes},
        )
        if self._normalize_epistemic_anchor_object(
            end_proposal, end_report, chapter_id=chapter.id, anchor_kind="CEN",
        ):
            end_report = validator.validate(
                end_proposal, before_end, {item.id for item in self.state.nodes},
            )
        if not end_report.passed:
            raise StorylinePlanningError(
                f"El CEN de {chapter.id} contradice el estado del mundo.",
                details={"issues": [item.model_dump() for item in end_report.issues]},
            )
        end = self._node(
            end_proposal, chapter, "CEN", global_order, len(chapter_cpns) + 2,
        )
        self.state.accept(end, self._links(end))
        self.nekg.apply(end)
        self._allocate_words(chapter, [begin, *chapter_cpns, end])
        self._checkpoint(on_checkpoint)

    def plan(
        self, outline: StoryOutlineArtifact, anchors: ChapterAnchorsArtifact,
        blueprint: NarrativeBlueprint, world: WorldArtifact, characters: StorylineCast,
        story_frame: StoryFrame, on_checkpoint=None,
        taxonomy_brief: TaxonomyBrief | None = None,
        taxonomy_application: TaxonomyApplication | None = None,
    ) -> tuple[IncrementalStorylineArtifact, NodeReviewHistory]:
        del blueprint
        self.state = StorylineState(outline.chapters)
        self.nekg = self._graph_factory(world, characters)
        self.history = NodeReviewHistory()
        validator = DependencyValidator(world, characters)
        by_chapter = {item.chapter_id: item for item in anchors.anchors}
        expected = [item.id for item in outline.chapters]
        actual = [item.chapter_id for item in anchors.anchors]
        if len(actual) != len(set(actual)) or set(actual) != set(expected):
            raise StorylinePlanningError(
                "Las anclas no corresponden exactamente con los capitulos del outline.",
                details={"chapter_ids": expected, "anchor_ids": actual},
            )

        for chapter in outline.chapters:
            baseline = self.state.clone()
            accepted_record_count = len(self.history.records)
            anchor = by_chapter[chapter.id]
            last_failure: Exception | None = None
            succeeded = False
            for chapter_attempt in range(self.max_chapter_replans + 1):
                self.state = baseline.clone()
                self.nekg = self._graph_from_state(world, characters, self.state)

                def reject_and_checkpoint(record: dict) -> None:
                    self._reject(record)
                    self._checkpoint(on_checkpoint)

                cpn_planner = CpnPlanner(
                    self.provider, CpnValidator(world, characters),
                    max_retries=self.max_retries, reviewer=self.reviewer,
                    emit=self._emit, reject=reject_and_checkpoint,
                )
                try:
                    self._plan_chapter(
                        chapter, anchor, world, characters, story_frame, cpn_planner,
                        validator, on_checkpoint, taxonomy_brief, taxonomy_application,
                        attempt_offset=chapter_attempt * (self.max_retries + 1),
                    )
                    by_chapter[chapter.id] = anchor
                    succeeded = True
                    break
                except (CpnAttemptsExhausted, StorylinePlanningError) as exc:
                    last_failure = exc
                    self.history.records = self.history.records[:accepted_record_count]
                    self.state = baseline.clone()
                    self.nekg = self._graph_from_state(world, characters, self.state)
                    self._emit(
                        "chapter_rolled_back",
                        f"capitulo {chapter.id} descartado antes de comprometer STORYLINE",
                        chapter_id=chapter.id,
                    )
                    self._checkpoint(on_checkpoint)
                    if chapter_attempt >= self.max_chapter_replans:
                        break
                    failures = [
                        item for item in self.history.rejected
                        if item.get("chapter_id") == chapter.id
                    ]
                    anchor = self._replacement_anchor(
                        chapter, outline, anchor, world, characters, story_frame, failures,
                    )
                    for index, item in enumerate(anchors.anchors):
                        if item.chapter_id == chapter.id:
                            anchors.anchors[index] = anchor
                            break
                    self._emit(
                        "chapter_replanned",
                        f"anclas de {chapter.id} regeneradas; reintentando el capitulo",
                        chapter_id=chapter.id,
                    )

            if not succeeded:
                failures = [
                    item for item in self.history.rejected
                    if item.get("chapter_id") == chapter.id
                ]
                issue_codes = sorted({
                    code for item in failures for code in item.get("issue_codes", [])
                })
                slot = (
                    last_failure.context.slot
                    if isinstance(last_failure, CpnAttemptsExhausted) else None
                )
                summary = (
                    f"No se pudo validar el CPN {chapter.id}:{slot}."
                    if slot is not None else str(last_failure)
                )
                raise StorylinePlanningError(
                    summary,
                    details={
                        "chapter_id": chapter.id, "slot": slot, "attempts": failures,
                        "issue_codes": issue_codes,
                        "chapter_failure": (
                            last_failure.details
                            if isinstance(last_failure, StorylinePlanningError) else None
                        ),
                        "chapter_replans": self.max_chapter_replans,
                        "checkpoints": "checkpoints/",
                        "attempt_artifacts": f"storyline_attempts/{chapter.id}/",
                    },
                ) from last_failure

        return self.state.artifact(), self.history
