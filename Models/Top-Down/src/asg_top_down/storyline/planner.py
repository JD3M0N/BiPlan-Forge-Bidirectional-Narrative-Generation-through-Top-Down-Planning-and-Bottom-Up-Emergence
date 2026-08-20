"""Adaptive factual STORYTELLER planner for Top-Down 4.0."""

from __future__ import annotations

import json
import math
from collections.abc import Callable

from pydantic import BaseModel, Field

from ..domain import (
    AgentStorySpec, ChapterPlan, StoryFrame, StorylineCast, StoryOutlineArtifact,
    StoryPlanArtifact, TaxonomyApplication, TaxonomyBrief, WorldArtifact,
)
from ..errors import StorylinePlanningError, StructuredResponseError
from ..narrative_db import NarrativeBlueprint
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
    ) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self._graph_factory = graph_factory
        self.reviewer = DramaticReviewer(provider)
        self.nekg: NarrativeGraphBackend = graph_factory()
        self.history = NodeReviewHistory()
        self.state = StorylineState([])

    def _checkpoint(self, callback) -> None:
        if callback:
            callback(self.state.artifact(), self.nekg.artifact(), self.history)

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
        requested = (
            f"Create exactly {request.requested_chapters} chapters."
            if request.requested_chapters else
            "Choose a compact chapter count that normally keeps chapters between 400 and 900 words."
        )
        return self.provider.generate_structured(
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
        return self.provider.generate_structured(
            system_instruction=(
                "Generate one concrete SVO internal plot event. Use canonical supplied entity and "
                "location IDs, explicit dependencies on accepted node IDs, typed factual "
                "preconditions, and typed state mutations. The event must follow character intention, "
                "meet active opposition, change state, avoid repetition, and advance toward the "
                f"chapter ending. {ending_rule} Taxonomy is a flexible palette, never a checklist. "
                "Return internal text in English."
            ),
            prompt=(
                f"CHAPTER:\n{_json(chapter)}\n\nBEGIN ANCHOR:\n{_json(anchor)}"
                f"\n\nEND TARGET:\n{_json({'subject': anchor.end_subject, 'verb': anchor.end_verb, 'object': anchor.end_object, 'location_id': anchor.end_location_id})}"
                f"\n\nSLOT: {slot}/{maximum}; MINIMUM: {minimum}"
                f"\n\nSTORY FRAME:\n{_json(story_frame)}"
                f"\n\nWORLD RULES AND MAP:\n{_json(world)}"
                f"\n\nCHARACTER FACTS:\n{_json(characters)}"
                f"\n\nRECENT ACCEPTED EVENTS:\n{_json(self.state.recent(8))}"
                f"\n\nACCEPTED CHAPTER EVENTS:\n{_json(chapter_cpns)}"
                f"\n\nCURRENT ENTITY STATE:\n{_json(self.nekg.snapshot())}"
                f"\n\nNARRATIVE PALETTE:\n{_json(_storyline_palette(taxonomy_brief))}"
                f"\n\nSELECTED MOVEMENT REFERENCES:\n"
                f"{_json(taxonomy_application.selected_movements) if taxonomy_application else 'none'}"
                f"\n\nREVISION FEEDBACK:\n{revision or 'none'}"
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
            begin_proposal = PlotNodeProposal(
                location_id=anchor.begin_location_id,
                subject=anchor.begin_subject, verb=anchor.begin_verb, object=anchor.begin_object,
                purpose="Establish the chapter's factual initial state",
                narrative_function="chapter_begin",
                depends_on_node_ids=[] if previous is None else [previous.id],
                effects=anchor.begin_effects,
                intention="Continue the active character goal",
                conflict="The central opposition remains active",
                consequence="The chapter's initial conditions become unavoidable",
            )
            begin = self._node(begin_proposal, chapter, "CBN", global_order, 1)
            begin_report = validator.validate(
                begin_proposal, self.nekg.snapshot(), {item.id for item in self.state.nodes},
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
                for attempt in range(1, self.max_retries + 2):
                    try:
                        proposal = self._proposal(
                            chapter, anchor, world, characters, story_frame,
                            chapter_cpns, revision, slot, minimum,
                            maximum, taxonomy_brief, taxonomy_application,
                        )
                    except StructuredResponseError as exc:
                        issue, validation = self._structured_rejection(exc, "candidate")
                        self.history.rejected.append({
                            "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                            "stage": "proposal", "issues": [issue], "validation": validation,
                        })
                        revision = issue
                        self._checkpoint(on_checkpoint)
                        continue

                    taxonomy_issue = self._taxonomy_issue(proposal, taxonomy_application)
                    dependency = validator.validate(
                        proposal, self.nekg.snapshot(), {item.id for item in self.state.nodes},
                    )
                    deterministic_issues = [item.message for item in dependency.issues]
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
                        self.history.rejected.append({
                            "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                            "stage": "dependency", "proposal": proposal.model_dump(mode="json"),
                            "issues": deterministic_issues,
                        })
                        revision = "; ".join(deterministic_issues)
                        self._checkpoint(on_checkpoint)
                        continue

                    try:
                        review = self.reviewer.review(
                            proposal, chapter, anchor, world, characters, dependency,
                            self.state.recent(8), self.nekg,
                        )
                    except StructuredResponseError as exc:
                        issue, validation = self._structured_rejection(exc, "review")
                        self.history.rejected.append({
                            "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                            "stage": "review", "proposal": proposal.model_dump(mode="json"),
                            "issues": [issue], "validation": validation,
                        })
                        revision = issue
                        self._checkpoint(on_checkpoint)
                        continue

                    candidate = review.revised or proposal
                    replacement_dependency = validator.validate(
                        candidate, self.nekg.snapshot(), {item.id for item in self.state.nodes},
                    )
                    post_issues = [item.message for item in replacement_dependency.issues]
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
                    self.history.rejected.append({
                        "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                        "stage": "review", "proposal": proposal.model_dump(mode="json"),
                        "review": review.model_dump(mode="json"),
                        "candidate": candidate.model_dump(mode="json"), "issues": issues,
                    })
                    revision = "; ".join(issues)
                    self._checkpoint(on_checkpoint)
                else:
                    raise StorylinePlanningError(
                        f"No se pudo validar el CPN {chapter.id}:{slot}.",
                        details={"chapter_id": chapter.id, "slot": slot},
                    )
                if aligned:
                    break
            if not aligned:
                raise StorylinePlanningError(
                    f"El capítulo {chapter.id} no conectó con su CEN dentro del límite.",
                    details={"chapter_id": chapter.id, "max_cpn": maximum},
                )

            end_proposal = PlotNodeProposal(
                location_id=anchor.end_location_id,
                subject=anchor.end_subject, verb=anchor.end_verb, object=anchor.end_object,
                purpose="Establish the chapter's factual end state",
                narrative_function="chapter_end",
                depends_on_node_ids=[previous.id] if previous else [],
                preconditions=anchor.end_preconditions, effects=anchor.end_effects,
                intention="Resolve or transform the active chapter goal",
                conflict="The outcome has a meaningful cost",
                consequence="The chapter ending changes the next chapter's conditions",
            )
            end_report = validator.validate(
                end_proposal, self.nekg.snapshot(), {item.id for item in self.state.nodes},
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
