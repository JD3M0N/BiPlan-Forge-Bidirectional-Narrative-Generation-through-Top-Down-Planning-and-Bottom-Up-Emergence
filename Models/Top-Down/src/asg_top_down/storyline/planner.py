"""Adaptive factual STORYTELLER planner for Top-Down 4.0."""

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
from ..errors import StorylinePlanningError, StructuredResponseError
from ..narrative_db import NarrativeBlueprint
from ..progress import PipelineEvent, PipelineEventCallback
from .dependency import DependencyValidator
from .graph import NarrativeEntityGraph, NarrativeGraphBackend
from .models import (
    AcceptedNodeRecord, ChapterAnchorsArtifact, IncrementalStorylineArtifact,
    NarrativeEdge, NodeGoal, PlotNode, PlotNodeProposal,
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
        if self._signature(node) in {self._signature(item) for item in self.nodes}:
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


def _storyline_palette(brief: TaxonomyBrief | None) -> dict | None:
    if brief is None:
        return None
    return {
        "movements": brief.movements,
        "complications": brief.complications,
        "conclusion": brief.conclusion,
        "freshness_choices": brief.freshness_choices,
        "avoid": brief.avoid,
        "usage_rule": brief.usage_rule,
    }


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
    ) -> None:
        self.provider = provider
        self.max_retries = max_retries
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
        subject = entities.get(anchor.end_subject.id)
        current = subject.state.get("location") if subject else None
        pre_cen_location = next((
            item.value for item in anchor.end_preconditions
            if item.entity_id == anchor.end_subject.id
            and item.attribute == "location" and item.operator == "equals"
        ), None) or anchor.end_location_id
        path = self._shortest_location_path(
            world, current, pre_cen_location,
        ) if current else []
        remaining_slots = maximum - slot + 1
        return {
            "subject_id": anchor.end_subject.id,
            "current_location": current,
            "pre_cen_location": pre_cen_location,
            "post_cen_location": anchor.end_location_id,
            "shortest_path": path,
            "remaining_cpn_slots": remaining_slots,
            "must_move_now": len(path) > 1 and len(path) - 1 >= remaining_slots,
            "required_next_location": path[1] if len(path) > 1 else None,
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

    @staticmethod
    def _structured_rejection(exc: StructuredResponseError, stage: str) -> tuple[str, dict]:
        return (
            f"The {stage} response was structurally invalid. Return a complete valid replacement.",
            {"error_code": exc.code, "error_stage": exc.stage, "details": exc.details},
        )

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

    def _proposal(
        self,
        chapter: ChapterPlan,
        anchor,
        world: WorldArtifact,
        characters: StorylineCast,
        story_frame: StoryFrame,
        chapter_cpns: list[PlotNode],
        revision: str,
        previous_proposal: PlotNodeProposal | None,
        slot: int,
        minimum: int,
        maximum: int,
        taxonomy_brief: TaxonomyBrief | None,
        taxonomy_application: TaxonomyApplication | None,
    ) -> PlotNodeProposal:
        ending_rule = (
            "The event may bridge immediately to the ending because the minimum development exists."
            if slot >= minimum else
            "The event must develop the conflict and must not bridge immediately to the ending yet."
        )
        if slot == maximum:
            ending_rule = "This final allowed event must create an immediate factual bridge to the ending."
        snapshot = self.nekg.snapshot()
        location_bridge = self._location_bridge(world, anchor, snapshot, slot, maximum)
        forbidden = [
            (anchor.begin_subject.id, anchor.begin_verb.casefold().strip(), anchor.begin_object.id),
            (anchor.end_subject.id, anchor.end_verb.casefold().strip(), anchor.end_object.id),
            *((item.subject.id, item.verb.casefold().strip(), item.object.id) for item in chapter_cpns),
        ]
        repair_rule = (
            "Rewrite and repair the previous candidate using every validation issue below. "
            if revision else ""
        )
        self._emit(
            "agent_called", "se llamo al agente plot_node_proposal",
            chapter_id=chapter.id,
        )
        return self.provider.generate_structured(
            system_instruction=(
                f"{repair_rule}Generate one concrete SVO internal plot event. "
                "Use canonical supplied entity and "
                "location IDs, explicit dependencies on accepted node IDs, typed factual "
                "preconditions, and typed state mutations. The event must follow character intention, "
                "meet active opposition, change state, avoid repetition, and advance toward the "
                f"chapter ending. {ending_rule} Taxonomy is a flexible palette, never a checklist. "
                "An object can only participate where its current state says it is located or owned. "
                "A movement event happens at the actor's current source location; represent the adjacent "
                "destination only as a location effect. If REQUIRED LOCATION BRIDGE says must_move_now, "
                "the event must move its subject to required_next_location. "
                "Never repeat a forbidden SVO. Return internal text in English."
            ),
            prompt=(
                f"CHAPTER:\n{_json(chapter)}\n\nBEGIN ANCHOR:\n{_json(anchor)}"
                f"\n\nEND TARGET:\n{_json({'subject': anchor.end_subject, 'verb': anchor.end_verb, 'object': anchor.end_object, 'location_id': anchor.end_location_id})}"
                f"\n\nCEN TARGET STATE:\n"
                f"{_json({'preconditions': anchor.end_preconditions, 'effects': anchor.end_effects})}"
                "\nDo not perform an exact CEN effect early. Its preconditions are targets for the "
                "state immediately before the CEN: intermediate values may evolve, and later CPNs "
                "must establish the exact required state."
                f"\n\nSLOT: {slot}/{maximum}; MINIMUM: {minimum}"
                f"\n\nSTORY FRAME:\n{_json(story_frame)}"
                f"\n\nWORLD RULES AND MAP:\n{_json(world)}"
                f"\n\nCHARACTER FACTS:\n{_json(characters)}"
                f"\n\nRECENT ACCEPTED EVENTS:\n{_json(self.state.recent(8))}"
                f"\n\nACCEPTED CHAPTER EVENTS:\n{_json(chapter_cpns)}"
                f"\n\nCURRENT ENTITY STATE (AUTHORITATIVE):\n{_json(snapshot)}"
                f"\n\nREQUIRED LOCATION BRIDGE:\n{_json(location_bridge)}"
                f"\n\nALLOWED DEPENDENCY IDS:\n{_json([item.id for item in self.state.nodes])}"
                f"\n\nFORBIDDEN SVO SIGNATURES:\n{_json(forbidden)}"
                f"\n\nNARRATIVE PALETTE:\n{_json(_storyline_palette(taxonomy_brief))}"
                f"\n\nSELECTED MOVEMENT REFERENCES:\n"
                f"{_json(taxonomy_application.selected_movements) if taxonomy_application else 'none'}"
                f"\n\nPREVIOUS REJECTED PROPOSAL:\n{_json(previous_proposal) if previous_proposal else 'none'}"
                f"\n\nREVISION FEEDBACK (ALL ITEMS ARE MANDATORY):\n{revision or 'none'}"
            ),
            schema=PlotNodeProposal,
        )

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

    @staticmethod
    def _taxonomy_issue(
        proposal: PlotNodeProposal, application: TaxonomyApplication | None,
    ) -> str | None:
        if not application or not (proposal.taxonomy_id or proposal.taxonomy_movement_id):
            return None
        selected = {
            (item.taxonomy_id, item.option_id) for item in application.selected_movements
        }
        reference = proposal.taxonomy_id, proposal.taxonomy_movement_id
        if None in reference or reference not in selected:
            return "candidate taxonomy reference must identify one selected movement or be empty"
        return None

    def plan(
        self,
        outline: StoryOutlineArtifact,
        anchors: ChapterAnchorsArtifact,
        blueprint: NarrativeBlueprint,
        world: WorldArtifact,
        characters: StorylineCast,
        story_frame: StoryFrame,
        on_checkpoint=None,
        taxonomy_brief: TaxonomyBrief | None = None,
        taxonomy_application: TaxonomyApplication | None = None,
    ) -> tuple[IncrementalStorylineArtifact, NodeReviewHistory]:
        del blueprint  # retrieval has already been compiled into the selected palette
        self.state = StorylineState(outline.chapters)
        self.nekg = self._graph_factory(world, characters)
        self.history = NodeReviewHistory()
        validator = DependencyValidator(world, characters)
        by_chapter = {item.chapter_id: item for item in anchors.anchors}
        expected = [item.id for item in outline.chapters]
        actual = [item.chapter_id for item in anchors.anchors]
        if len(actual) != len(set(actual)) or set(actual) != set(expected):
            raise StorylinePlanningError(
                "Las anclas no corresponden exactamente con los capítulos del outline.",
                details={"chapter_ids": expected, "anchor_ids": actual},
            )

        global_order = 1
        previous: PlotNode | None = None
        for chapter in outline.chapters:
            anchor = by_chapter[chapter.id]
            before_begin = self.nekg.snapshot()
            begin_effects = self._effective_anchor_effects(
                anchor.begin_effects, before_begin,
                anchor.begin_subject, anchor.begin_verb, anchor.begin_object,
                chapter_id=chapter.id, anchor_kind="CBN",
            )
            begin_proposal = PlotNodeProposal(
                location_id=anchor.begin_location_id,
                subject=anchor.begin_subject, verb=anchor.begin_verb, object=anchor.begin_object,
                purpose="Establish the chapter's factual initial state",
                narrative_function="chapter_begin",
                depends_on_node_ids=[] if previous is None else [previous.id],
                effects=begin_effects,
                intention="Continue the active character goal",
                conflict="The central opposition remains active",
                consequence="The chapter's initial conditions become unavoidable",
            )
            begin = self._node(begin_proposal, chapter, "CBN", global_order, 1)
            begin_report = validator.validate(
                begin_proposal, before_begin, {item.id for item in self.state.nodes},
            )
            if not begin_report.passed:
                raise StorylinePlanningError(
                    f"El CBN de {chapter.id} contradice el estado del mundo.",
                    details={"issues": [item.model_dump() for item in begin_report.issues]},
                )
            self.state.accept(begin, self._links(begin))
            self.nekg.apply(begin)
            previous = begin
            global_order += 1
            self._checkpoint(on_checkpoint)

            chapter_cpns: list[PlotNode] = []
            minimum, maximum = self.min_cpn_count(chapter), self.max_cpn_count(chapter)
            aligned = False
            for slot in range(1, maximum + 1):
                revision = ""
                previous_proposal: PlotNodeProposal | None = None
                for attempt in range(1, self.max_retries + 2):
                    try:
                        proposal = self._proposal(
                            chapter, anchor, world, characters, story_frame,
                            chapter_cpns, revision, previous_proposal, slot, minimum,
                            maximum, taxonomy_brief, taxonomy_application,
                        )
                    except StructuredResponseError as exc:
                        issue, validation = self._structured_rejection(exc, "candidate")
                        self._reject({
                            "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                            "stage": "proposal", "issues": [issue], "validation": validation,
                        })
                        revision = issue
                        self._checkpoint(on_checkpoint)
                        continue

                    current_snapshot = self.nekg.snapshot()
                    self._normalize_movement_origin(
                        proposal, current_snapshot, chapter_id=chapter.id,
                    )

                    taxonomy_issue = self._taxonomy_issue(proposal, taxonomy_application)
                    dependency = validator.validate(
                        proposal, current_snapshot, {item.id for item in self.state.nodes},
                    )
                    deterministic_issues = [item.message for item in dependency.issues]
                    deterministic_issues.extend(
                        self._cen_reservation_issues(proposal, anchor)
                    )
                    bridge = self._location_bridge(
                        world, anchor, current_snapshot, slot, maximum,
                    )
                    movement_destination = next((
                        item.value for item in proposal.effects
                        if item.entity_id == bridge["subject_id"]
                        and item.attribute == "location"
                    ), None)
                    if bridge["must_move_now"] and movement_destination != bridge["required_next_location"]:
                        deterministic_issues.append(
                            "candidate must move the ending subject from "
                            f"{bridge['current_location']} to adjacent "
                            f"{bridge['required_next_location']} in this slot"
                        )
                    if taxonomy_issue:
                        deterministic_issues.append(taxonomy_issue)
                    signature = (proposal.subject.id, proposal.verb.casefold().strip(), proposal.object.id)
                    forbidden = {
                        (anchor.begin_subject.id, anchor.begin_verb.casefold().strip(), anchor.begin_object.id),
                        (anchor.end_subject.id, anchor.end_verb.casefold().strip(), anchor.end_object.id),
                        *((item.subject.id, item.verb.casefold().strip(), item.object.id) for item in chapter_cpns),
                    }
                    if signature in forbidden:
                        deterministic_issues.append("candidate repeats an anchor or accepted chapter event")
                    if deterministic_issues:
                        self._reject({
                            "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                            "stage": "dependency", "proposal": proposal.model_dump(mode="json"),
                            "validation_codes": [item.code for item in dependency.issues],
                            "issues": deterministic_issues,
                        })
                        revision = "; ".join(deterministic_issues)
                        previous_proposal = proposal
                        self._checkpoint(on_checkpoint)
                        continue

                    try:
                        self._emit(
                            "agent_called", "se llamo al agente dramatic_reviewer",
                            chapter_id=chapter.id, attempt=attempt,
                        )
                        review = self.reviewer.review(
                            proposal, chapter, anchor, world, characters, dependency,
                            self.state.recent(8), self.nekg,
                            alignment_allowed=slot >= minimum,
                        )
                    except StructuredResponseError as exc:
                        issue, validation = self._structured_rejection(exc, "review")
                        self._reject({
                            "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                            "stage": "review", "proposal": proposal.model_dump(mode="json"),
                            "issues": [issue], "validation": validation,
                        })
                        revision = issue
                        self._checkpoint(on_checkpoint)
                        continue

                    if slot < minimum:
                        alignment_issues = [
                            issue for issue in review.issues
                            if "aligns_with_cen" in issue.casefold()
                            or (
                                "minimum" in issue.casefold()
                                and "chapter" in issue.casefold()
                            )
                        ]
                        normalized = review.aligns_with_cen
                        review.aligns_with_cen = False
                        review_checks = (
                            review.causal, review.intentional, review.conflict_present,
                            review.continuous, review.novel, review.advances_ending,
                            review.world_consistent, review.emotionally_effective,
                        )
                        if (
                            not review.accepted
                            and review.issues
                            and len(alignment_issues) == len(review.issues)
                            and all(review_checks)
                        ):
                            review.accepted = True
                            review.issues = []
                            normalized = True
                        if normalized:
                            self._emit(
                                "review_normalized",
                                f"CPN {chapter.id}:{slot}: alineacion aplazada hasta el minimo",
                                chapter_id=chapter.id, attempt=attempt,
                            )
                    candidate = review.revised or proposal
                    self._normalize_movement_origin(
                        candidate, current_snapshot, chapter_id=chapter.id,
                    )
                    replacement_dependency = validator.validate(
                        candidate, current_snapshot, {item.id for item in self.state.nodes},
                    )
                    post_issues = [item.message for item in replacement_dependency.issues]
                    post_issues.extend(self._cen_reservation_issues(candidate, anchor))
                    replacement_taxonomy_issue = self._taxonomy_issue(candidate, taxonomy_application)
                    if replacement_taxonomy_issue:
                        post_issues.append(replacement_taxonomy_issue)
                    replacement_signature = (
                        candidate.subject.id, candidate.verb.casefold().strip(), candidate.object.id,
                    )
                    if replacement_signature in forbidden:
                        post_issues.append(
                            "reviewer replacement repeats an anchor or accepted chapter event"
                        )
                    final_without_alignment = slot == maximum and not review.aligns_with_cen
                    too_early = review.aligns_with_cen and slot < minimum
                    if review.accepted and not post_issues and not final_without_alignment and not too_early:
                        node = self._node(candidate, chapter, "CPN", global_order, slot + 1)
                        self.state.accept(node, self._links(node))
                        self.nekg.apply(node)
                        self.history.records.append(AcceptedNodeRecord(
                            node=node, review=review, attempt=attempt,
                        ))
                        chapter_cpns.append(node)
                        previous = node
                        global_order += 1
                        aligned = review.aligns_with_cen and len(chapter_cpns) >= minimum
                        self._checkpoint(on_checkpoint)
                        break

                    issues = [*review.issues, *post_issues]
                    if too_early:
                        issues.append("minimum chapter development has not been reached")
                    if final_without_alignment:
                        issues.append("final candidate does not bridge immediately to the ending")
                    self._reject({
                        "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                        "stage": "review", "proposal": proposal.model_dump(mode="json"),
                        "review": review.model_dump(mode="json"),
                        "candidate": candidate.model_dump(mode="json"), "issues": issues,
                    })
                    revision = "; ".join(issues)
                    previous_proposal = candidate
                    self._checkpoint(on_checkpoint)
                else:
                    attempts = [
                        item for item in self.history.rejected
                        if item.get("chapter_id") == chapter.id and item.get("slot") == slot
                    ]
                    raise StorylinePlanningError(
                        f"No se pudo validar el CPN {chapter.id}:{slot}.",
                        details={
                            "chapter_id": chapter.id, "slot": slot,
                            "attempts": attempts,
                            "checkpoints": "checkpoints/",
                            "attempt_artifacts": f"storyline_attempts/{chapter.id}/slot-{slot:02d}/",
                        },
                    )
                if aligned:
                    break
            if not aligned:
                raise StorylinePlanningError(
                    f"El capítulo {chapter.id} no conectó con su CEN dentro del límite.",
                    details={"chapter_id": chapter.id, "max_cpn": maximum},
                )

            before_end = self.nekg.snapshot()
            end_effects = self._effective_anchor_effects(
                anchor.end_effects, before_end,
                anchor.end_subject, anchor.end_verb, anchor.end_object,
                chapter_id=chapter.id, anchor_kind="CEN",
            )
            end_proposal = PlotNodeProposal(
                location_id=anchor.end_location_id,
                subject=anchor.end_subject, verb=anchor.end_verb, object=anchor.end_object,
                purpose="Establish the chapter's factual end state",
                narrative_function="chapter_end",
                depends_on_node_ids=[previous.id] if previous else [],
                preconditions=anchor.end_preconditions, effects=end_effects,
                intention="Resolve or transform the active chapter goal",
                conflict="The outcome has a meaningful cost",
                consequence="The chapter ending changes the next chapter's conditions",
            )
            self._normalize_movement_origin(
                end_proposal, before_end, chapter_id=chapter.id,
            )
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
            previous = end
            global_order += 1
            self._checkpoint(on_checkpoint)

        return self.state.artifact(), self.history
