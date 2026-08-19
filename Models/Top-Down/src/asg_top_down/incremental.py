"""Adaptive STORYTELLER planner with live STORYLINE and NEKG feedback."""

from __future__ import annotations

import json
import math
from collections.abc import Callable

from pydantic import BaseModel, Field

from .errors import StorylinePlanningError, StructuredResponseError
from .narrative_db import NarrativeBlueprint
from .nekg import NarrativeEntityGraph, NarrativeGraphBackend
from .schemas import (
    AcceptedNodeRecord, ChapterAnchorsArtifact, ChapterPlan, CharactersArtifact,
    IncrementalStorylineArtifact, NarrativeEdge, NodeGoal, PlotNode,
    PlotNodeProposal, PlotNodeReview, StoryOutlineArtifact, StoryPlanArtifact,
    StoryRequest, StorylineObligation, StorylineObligationsArtifact,
    TaxonomyApplication, TaxonomyBrief, WorldArtifact,
)


class NodeReviewHistory(BaseModel):
    records: list[AcceptedNodeRecord] = Field(default_factory=list)
    rejected: list[dict] = Field(default_factory=list)


class StorylineState:
    def __init__(self, chapters: list[ChapterPlan]) -> None:
        self.chapters = chapters
        self.nodes: list[PlotNode] = []
        self.edges: list[NarrativeEdge] = []

    def accept(self, node: PlotNode, causal_links: list[NarrativeEdge]) -> None:
        known = {item.id for item in self.nodes}
        if node.id in known:
            raise ValueError(f"duplicate storyline node: {node.id}")
        if any(edge.target != node.id or edge.source not in known for edge in causal_links):
            raise ValueError("new causal links must connect accepted history to the new node")
        self.nodes.append(node)
        self.edges.extend(causal_links)

    def recent(self, limit: int = 8) -> list[PlotNode]:
        return self.nodes[-limit:]

    def artifact(self) -> IncrementalStorylineArtifact:
        return IncrementalStorylineArtifact(
            chapters=self.chapters,
            nodes=self.nodes,
            accepted_edges=self.edges,
            topological_order=[item.id for item in self.nodes],
        )


def _json(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                 for item in value]
    return json.dumps(value, ensure_ascii=False, indent=2)


class IncrementalPlotPlanner:
    """Paper-faithful CBN/CPN/CEN planning with bounded adaptive termination."""

    def __init__(
        self,
        provider,
        *,
        max_retries: int = 2,
        graph_factory: Callable[[], NarrativeGraphBackend] = NarrativeEntityGraph,
    ) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self._graph_factory = graph_factory
        self.nekg = graph_factory()
        self.history = NodeReviewHistory()
        self.state = StorylineState([])
        self._checkpoint_callback = None

    def _checkpoint(self, callback) -> None:
        if callback:
            callback(self.state.artifact(), self.nekg.artifact(), self.history)

    @staticmethod
    def _structured_rejection(exc: StructuredResponseError, stage: str) -> tuple[str, dict]:
        validation = {
            "error_code": exc.code,
            "error_stage": exc.stage,
            "details": exc.details,
        }
        issue = (
            f"The {stage} response was structurally invalid. Return a complete valid replacement."
        )
        return issue, validation

    def outline(
        self,
        request: StoryRequest,
        plan: StoryPlanArtifact,
        blueprint: NarrativeBlueprint,
        repair_feedback: str = "",
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> StoryOutlineArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Create the high-level STORYTELLER frame before creating plot nodes. Produce one "
                "premise, a complete synopsis, and all ordered chapter titles and abstracts. Allocate "
                "exactly the requested total words. Use retrieved knowledge as flexible guidance rather "
                "than literal prose. Ensure escalation, a consequential climax, and enough aftermath. "
                "Write premise, synopsis, and chapter abstracts in English. Write each chapter title "
                "in the requested fiction language because it will appear verbatim in the final story."
            ),
            prompt=(f"REQUEST:\n{_json(request)}\n\nPLAN:\n{_json(plan)}"
                    f"\n\nRETRIEVED KNOWLEDGE:\n{_json(blueprint.model_context())}"
                    f"\n\nSELECTED TAXONOMY BRIEF:\n{_json(taxonomy_brief) if taxonomy_brief else 'none'}"
                    f"{repair_feedback}"),
            schema=StoryOutlineArtifact,
        )

    def anchors(
        self,
        outline: StoryOutlineArtifact,
        world: WorldArtifact,
        characters: CharactersArtifact,
        obligations: StorylineObligationsArtifact | None = None,
        repair_feedback: str = "",
    ) -> ChapterAnchorsArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Generate exactly one concrete SVO chapter-begin node and one concrete SVO chapter-end "
                "node for every chapter before generating any internal plot nodes. Use the current, "
                "preceding, and following chapter abstracts so adjacent states connect smoothly. "
                "Make the events realize the supplied neutral narrative obligations without exposing "
                "their IDs. Describe observable events rather than themes or writing instructions. "
                "Return all artifact text in English."
            ),
            prompt=(f"OUTLINE:\n{_json(outline)}\n\nWORLD:\n{_json(world)}"
                    f"\n\nCHARACTERS:\n{_json(characters)}"
                    f"\n\nNARRATIVE OBLIGATIONS:\n{_json(obligations) if obligations else 'none'}"
                    f"{repair_feedback}"),
            schema=ChapterAnchorsArtifact,
        )

    @staticmethod
    def max_cpn_count(chapter: ChapterPlan) -> int:
        return max(1, min(10, math.ceil(chapter.target_words / 350)))

    @staticmethod
    def cpn_budget(chapter: ChapterPlan) -> int:
        """Compatibility name for the adaptive safety ceiling."""
        return IncrementalPlotPlanner.max_cpn_count(chapter)

    @staticmethod
    def _node(
        proposal: PlotNodeProposal,
        chapter: ChapterPlan,
        kind: str,
        global_order: int,
        local_order: int,
    ) -> PlotNode:
        return PlotNode(
            id=f"n_{global_order:04d}",
            chapter_id=chapter.id,
            node_type=kind,
            subject=proposal.subject,
            verb=proposal.verb,
            object=proposal.object,
            timestamp=global_order - 1,
            global_order=global_order,
            local_order=local_order,
            target_words=1,
            preconditions=proposal.preconditions,
            effects=proposal.effects,
            intention=proposal.intention,
            conflict=proposal.conflict,
            goals=[NodeGoal(
                purpose=proposal.purpose,
                taxonomy_id=proposal.taxonomy_id,
                taxonomy_movement_id=proposal.taxonomy_movement_id,
                archetype_id="composed" if proposal.schema_beat_id else None,
                schema_beat_id=proposal.schema_beat_id,
                success_criteria=["The event causes an observable state change"],
            )],
        )

    def _proposal(
        self,
        chapter: ChapterPlan,
        anchor,
        blueprint: NarrativeBlueprint,
        chapter_cpns: list[PlotNode],
        revision: str,
        slot: int,
        maximum: int,
        taxonomy_brief: TaxonomyBrief | None = None,
        taxonomy_application: TaxonomyApplication | None = None,
        obligations: list[StorylineObligation] | None = None,
    ) -> PlotNodeProposal:
        final_instruction = (
            " This is the final allowed slot, so the event must create a natural immediate bridge to "
            "the supplied chapter-end node."
            if slot == maximum else
            " Do not jump to the chapter-end node before enough causal development has occurred."
        )
        return self.provider.generate_structured(
            system_instruction=(
                "Generate one pseudo chapter-plot node as a concrete SVO event. Base it on the "
                "chapter-begin node, the pre-generated chapter-end target, and accepted internal nodes. "
                "The event must be caused or enabled by accepted history, follow a character intention, "
                "meet active opposition, change story state, and avoid repeating prior events. It must "
                "advance the supplied neutral narrative obligations naturally without exposing IDs."
                " When the event realizes a selected taxonomy movement, copy its taxonomy ID and "
                "movement ID into taxonomy_id and taxonomy_movement_id. Do not force a taxonomy "
                "movement merely to fill a slot and do not treat the brief as a fixed sequence."
                " Return all artifact text in English."
                + final_instruction
            ),
            prompt=(
                f"CHAPTER:\n{_json(chapter)}\n\nBEGIN NODE:\n{_json({
                    'subject': anchor.begin_subject, 'verb': anchor.begin_verb,
                    'object': anchor.begin_object,
                })}"
                f"\n\nEND NODE TARGET:\n{_json({
                    'subject': anchor.end_subject, 'verb': anchor.end_verb,
                    'object': anchor.end_object,
                })}"
                f"\n\nSLOT: {slot}/{maximum}\n\nACCEPTED CHAPTER PLOT NODES:\n{_json(chapter_cpns)}"
                f"\n\nRETRIEVED KNOWLEDGE:\n{_json(blueprint.model_context())}"
                f"\n\nSELECTED TAXONOMY BRIEF:\n{_json(taxonomy_brief) if taxonomy_brief else 'none'}"
                f"\n\nSELECTED TAXONOMY REFERENCES:\n"
                f"{_json(taxonomy_application) if taxonomy_application else 'none'}"
                f"\n\nCHAPTER NARRATIVE OBLIGATIONS:\n{_json(obligations or [])}"
                f"\n\nREVISION FEEDBACK:\n{revision or 'none'}"
            ),
            schema=PlotNodeProposal,
        )

    def _review(
        self, proposal: PlotNodeProposal, chapter: ChapterPlan, anchor,
        obligations: list[StorylineObligation] | None = None,
    ) -> PlotNodeReview:
        related = self.nekg.related(proposal.subject, proposal.object, limit=10)
        return self.provider.generate_structured(
            system_instruction=(
                "Review one pseudo chapter-plot node using recent STORYLINE events and NEKG relations. "
                "Accept only when the final candidate passes all seven semantic checks: causal support, "
                "character intention, active conflict, continuity, novelty, progress toward the chapter "
                "ending and supplied narrative obligations, and world consistency. If repairable, "
                "return a complete replacement candidate. "
                "Classify relevant review work as theme, logic, emotion, mystery, plot_resolution, "
                "language, or redundancy. Set aligns_with_cen only when the final candidate makes the "
                "pre-generated ending a natural immediate next event. Every boolean must evaluate the "
                "replacement when revised is present, otherwise the submitted proposal. Return all "
                "review and replacement text in English."
            ),
            prompt=(
                f"PROPOSAL:\n{_json(proposal)}\n\nCHAPTER:\n{_json(chapter)}"
                f"\n\nEND NODE TARGET:\n{_json({
                    'subject': anchor.end_subject, 'verb': anchor.end_verb,
                    'object': anchor.end_object,
                })}"
                f"\n\nRECENT STORYLINE EVENTS:\n{_json(self.state.recent(8))}"
                f"\n\nRELATED NEKG RELATIONS:\n{_json(related)}"
                f"\n\nCHAPTER NARRATIVE OBLIGATIONS:\n{_json(obligations or [])}"
            ),
            schema=PlotNodeReview,
        )

    @staticmethod
    def _allocate_words(chapter: ChapterPlan, nodes: list[PlotNode]) -> None:
        base, remainder = divmod(chapter.target_words, len(nodes))
        for node in nodes:
            node.target_words = max(1, base)
        nodes[-1].target_words += remainder

    def plan(
        self,
        outline: StoryOutlineArtifact,
        anchors: ChapterAnchorsArtifact,
        blueprint: NarrativeBlueprint,
        obligations: StorylineObligationsArtifact | None = None,
        on_checkpoint=None,
        taxonomy_brief: TaxonomyBrief | None = None,
        taxonomy_application: TaxonomyApplication | None = None,
    ) -> tuple[IncrementalStorylineArtifact, NodeReviewHistory]:
        self.state = StorylineState(outline.chapters)
        self.nekg = self._graph_factory()
        self.history = NodeReviewHistory()
        by_chapter = {item.chapter_id: item for item in anchors.anchors}
        obligations_by_chapter = {
            chapter.id: [item for item in (obligations.obligations if obligations else [])
                         if item.chapter_id == chapter.id]
            for chapter in outline.chapters
        }
        expected = [chapter.id for chapter in outline.chapters]
        actual = [anchor.chapter_id for anchor in anchors.anchors]
        if len(actual) != len(set(actual)) or set(actual) != set(expected) or len(actual) != len(expected):
            raise StorylinePlanningError(
                "Las anclas no corresponden exactamente con los capítulos del outline.",
                details={"chapter_ids": expected, "anchor_ids": actual},
                recommendations=["Regenera las anclas de capítulos."],
            )

        global_order = 1
        previous: PlotNode | None = None
        for chapter in outline.chapters:
            anchor = by_chapter[chapter.id]
            chapter_obligations = obligations_by_chapter[chapter.id]
            begin_proposal = PlotNodeProposal(
                subject=anchor.begin_subject,
                verb=anchor.begin_verb,
                object=anchor.begin_object,
                purpose="Establish the chapter state",
                schema_beat_id="chapter_begin",
                preconditions=["The prior chapter state, or the initial story state"],
                effects=["The chapter's initial state is established"],
                intention="Continue the active character goal",
                conflict="The central opposition remains active",
            )
            begin = self._node(begin_proposal, chapter, "CBN", global_order, 1)
            links = [] if previous is None else [NarrativeEdge(
                source=previous.id,
                target=begin.id,
                relation="enables",
                strength=5,
                rationale="The previous chapter state enables this beginning",
            )]
            self.state.accept(begin, links)
            self.nekg.apply(begin)
            previous = begin
            global_order += 1
            self._checkpoint(on_checkpoint)

            chapter_cpns: list[PlotNode] = []
            maximum = self.max_cpn_count(chapter)
            aligned = False
            for slot in range(1, maximum + 1):
                revision = ""
                for attempt in range(1, self.max_retries + 2):
                    try:
                        proposal = self._proposal(
                            chapter, anchor, blueprint, chapter_cpns, revision, slot, maximum,
                            taxonomy_brief, taxonomy_application, chapter_obligations,
                        )
                    except StructuredResponseError as exc:
                        issue, validation = self._structured_rejection(exc, "proposal")
                        self.history.rejected.append({
                            "chapter_id": chapter.id,
                            "slot": slot,
                            "attempt": attempt,
                            "stage": "proposal",
                            "proposal": None,
                            "review": None,
                            "candidate": None,
                            "issues": [issue],
                            "validation": validation,
                        })
                        revision = issue
                        self._checkpoint(on_checkpoint)
                        continue
                    if taxonomy_application and (
                        proposal.taxonomy_id or proposal.taxonomy_movement_id
                    ):
                        selected = {
                            (item.taxonomy_id, item.option_id)
                            for item in taxonomy_application.selected_movements
                        }
                        reference = (
                            proposal.taxonomy_id, proposal.taxonomy_movement_id,
                        )
                        if None in reference or reference not in selected:
                            issue = (
                                "The proposal taxonomy reference must identify one selected movement "
                                "or leave both taxonomy fields empty."
                            )
                            self.history.rejected.append({
                                "chapter_id": chapter.id,
                                "slot": slot,
                                "attempt": attempt,
                                "stage": "taxonomy_reference",
                                "proposal": proposal.model_dump(mode="json"),
                                "review": None,
                                "candidate": proposal.model_dump(mode="json"),
                                "issues": [issue],
                            })
                            revision = issue
                            self._checkpoint(on_checkpoint)
                            continue
                    try:
                        review = self._review(proposal, chapter, anchor, chapter_obligations)
                    except StructuredResponseError as exc:
                        issue, validation = self._structured_rejection(exc, "review")
                        self.history.rejected.append({
                            "chapter_id": chapter.id,
                            "slot": slot,
                            "attempt": attempt,
                            "stage": "review",
                            "proposal": proposal.model_dump(mode="json"),
                            "review": None,
                            "candidate": proposal.model_dump(mode="json"),
                            "issues": [issue],
                            "validation": validation,
                        })
                        revision = issue
                        self._checkpoint(on_checkpoint)
                        continue

                    candidate = review.revised if review.revised is not None else proposal
                    candidate_source = "review.revised" if review.revised is not None else "proposal"
                    final_without_alignment = slot == maximum and not review.aligns_with_cen
                    if review.accepted and not final_without_alignment:
                        node = self._node(candidate, chapter, "CPN", global_order, slot + 1)
                        assert previous is not None
                        link = NarrativeEdge(
                            source=previous.id,
                            target=node.id,
                            relation="causes",
                            strength=5,
                            rationale=f"Accepted effects of {previous.id} produce or motivate this event",
                        )
                        self.state.accept(node, [link])
                        self.nekg.apply(node, candidate.state_changes)
                        self.history.records.append(AcceptedNodeRecord(
                            node=node,
                            state_changes=candidate.state_changes,
                            review=review,
                            attempt=attempt,
                        ))
                        chapter_cpns.append(node)
                        previous = node
                        global_order += 1
                        aligned = review.aligns_with_cen
                        self._checkpoint(on_checkpoint)
                        break

                    issues = list(review.issues)
                    if final_without_alignment:
                        issues.append("The final candidate does not create an immediate bridge to the chapter end")
                    self.history.rejected.append({
                        "chapter_id": chapter.id,
                        "slot": slot,
                        "attempt": attempt,
                        "stage": "review",
                        "proposal": proposal.model_dump(mode="json"),
                        "review": review.model_dump(mode="json"),
                        "candidate": candidate.model_dump(mode="json"),
                        "candidate_source": candidate_source,
                        "issues": issues,
                    })
                    revision = "; ".join(issues)
                    self._checkpoint(on_checkpoint)
                else:
                    rejected = [item for item in self.history.rejected
                                if item.get("chapter_id") == chapter.id and item.get("slot") == slot]
                    raise StorylinePlanningError(
                        f"No se pudo validar el CPN {chapter.id}:{slot} después de "
                        f"{self.max_retries + 1} intentos.",
                        details={
                            "chapter_id": chapter.id,
                            "slot": slot,
                            "attempts": self.max_retries + 1,
                            "rejections": rejected,
                        },
                        recommendations=[
                            "Revisa proposal, review y candidate en planning_checkpoint/node_reviews.json."
                        ],
                    )
                if aligned:
                    break
            if not aligned:
                raise StorylinePlanningError(
                    f"El capítulo {chapter.id} alcanzó el límite de CPN sin conectar con su CEN.",
                    details={"chapter_id": chapter.id, "max_cpn": maximum},
                    recommendations=["Revisa el CEN y las revisiones guardadas en el checkpoint."],
                )

            end_proposal = PlotNodeProposal(
                subject=anchor.end_subject,
                verb=anchor.end_verb,
                object=anchor.end_object,
                purpose="Establish the chapter ending",
                schema_beat_id="chapter_end",
                preconditions=["Accepted chapter-plot-node consequences"],
                effects=["The chapter end state is established"],
                intention="Resolve or transform the active chapter goal",
                conflict="The outcome has a meaningful cost",
            )
            end = self._node(end_proposal, chapter, "CEN", global_order, len(chapter_cpns) + 2)
            assert previous is not None
            self.state.accept(end, [NarrativeEdge(
                source=previous.id,
                target=end.id,
                relation="causes",
                strength=5,
                rationale="The final accepted chapter event produces the pre-generated ending",
            )])
            self.nekg.apply(end)
            chapter_nodes = [begin, *chapter_cpns, end]
            self._allocate_words(chapter, chapter_nodes)
            previous = end
            global_order += 1
            self._checkpoint(on_checkpoint)

        return self.state.artifact(), self.history
