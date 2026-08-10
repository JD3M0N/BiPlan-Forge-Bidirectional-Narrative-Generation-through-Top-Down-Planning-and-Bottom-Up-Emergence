"""Incremental CPN planner with live STORYLINE and NEKG feedback."""

from __future__ import annotations

import json
import math

from pydantic import BaseModel, Field

from .nekg import NarrativeEntityGraph
from .narrative_db import NarrativeBlueprint
from .schemas import (
    AcceptedNodeRecord, ChapterAnchorsArtifact, ChapterPlan, CharactersArtifact,
    IncrementalStorylineArtifact, NarrativeEdge, NodeGoal, PlotNode,
    PlotNodeProposal, PlotNodeReview, StoryOutlineArtifact, StoryPlanArtifact,
    StoryRequest, WorldArtifact,
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
        known = {x.id for x in self.nodes}
        if node.id in known:
            raise ValueError(f"duplicate storyline node: {node.id}")
        if any(edge.target != node.id or edge.source not in known for edge in causal_links):
            raise ValueError("new causal links must connect known history to the accepted node")
        self.nodes.append(node)
        self.edges.extend(causal_links)

    def recent(self, limit: int = 8) -> list[PlotNode]:
        return self.nodes[-limit:]

    def artifact(self) -> IncrementalStorylineArtifact:
        return IncrementalStorylineArtifact(chapters=self.chapters, nodes=self.nodes,
            accepted_edges=self.edges, topological_order=[x.id for x in self.nodes])


def _json(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in value]
    return json.dumps(value, ensure_ascii=False, indent=2)


class IncrementalPlotPlanner:
    def __init__(self, provider, *, max_retries: int = 2) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self.nekg = NarrativeEntityGraph()
        self.history = NodeReviewHistory()

    def outline(self, request: StoryRequest, plan: StoryPlanArtifact,
                blueprint: NarrativeBlueprint) -> StoryOutlineArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Create the high-level STORYTELLER frame. Produce a premise, a complete synopsis, "
                "and ordered chapter abstracts before creating plot nodes. Allocate exactly the "
                "requested total words. Use retrieved narrative knowledge as flexible design guidance, "
                "never as a checklist or literal prose. Ensure escalation, a consequential climax, "
                "and enough space for aftermath. Output story content in the requested language."
            ),
            prompt=f"REQUEST:\n{_json(request)}\nPLAN:\n{_json(plan)}\nRETRIEVED KNOWLEDGE:\n{_json(blueprint)}",
            schema=StoryOutlineArtifact,
        )

    def anchors(self, outline: StoryOutlineArtifact, world: WorldArtifact,
                characters: CharactersArtifact) -> ChapterAnchorsArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Generate exactly one SVO begin anchor and one SVO end anchor for every chapter. "
                "Consider the preceding and following chapter abstracts so adjacent states connect. "
                "Anchors describe concrete observable events, not themes or narration instructions."
            ),
            prompt=f"OUTLINE:\n{_json(outline)}\nWORLD:\n{_json(world)}\nCHARACTERS:\n{_json(characters)}",
            schema=ChapterAnchorsArtifact,
        )

    @staticmethod
    def cpn_budget(chapter: ChapterPlan) -> int:
        # Short chapters benefit from fewer, better-developed events.
        return max(1, min(6, math.ceil(chapter.target_words / 450)))

    def _node(self, proposal: PlotNodeProposal, chapter: ChapterPlan, kind: str,
              global_order: int, local_order: int, target_words: int) -> PlotNode:
        return PlotNode(
            id=f"n_{global_order:04d}", chapter_id=chapter.id, node_type=kind,
            subject=proposal.subject, verb=proposal.verb, object=proposal.object,
            timestamp=global_order - 1, global_order=global_order, local_order=local_order,
            target_words=max(1, target_words), preconditions=proposal.preconditions,
            effects=proposal.effects, intention=proposal.intention, conflict=proposal.conflict,
            goals=[NodeGoal(purpose=proposal.purpose, archetype_id="composed",
                            taxonomy_beat=proposal.schema_beat_id,
                            success_criteria=["The event causes an observable state change"])],
        )

    def _proposal(self, chapter, end, blueprint, revision, slot, budget) -> PlotNodeProposal:
        recent = self.state.recent()
        return self.provider.generate_structured(
            system_instruction=(
                "Generate one pseudo-CPN as a concrete SVO event. It must be caused or enabled by "
                "accepted events, follow a character intention, meet active opposition, change story "
                "state, and move toward the chapter end without jumping there prematurely. Avoid "
                "rephrasing prior events. Instantiate retrieved beats for this story; do not copy them."
            ),
            prompt=(f"CHAPTER:\n{_json(chapter)}\nEND ANCHOR:\n{_json(end)}\nSLOT: {slot}/{budget}\n"
                    f"RECENT STORYLINE:\n{_json(recent)}\nRELATED NEKG:\n{_json(self.nekg.artifact())}\n"
                    f"BLUEPRINT:\n{_json(blueprint)}\nREVISION FEEDBACK:\n{revision or 'none'}"),
            schema=PlotNodeProposal,
        )

    def _review(self, proposal, chapter, end) -> PlotNodeReview:
        related = self.nekg.related(proposal.subject, proposal.object)
        return self.provider.generate_structured(
            system_instruction=(
                "Review one pseudo-CPN independently. Accept only if all seven checks pass: causal "
                "support, character intention, active conflict, continuity, novelty, progress toward "
                "the chapter ending, and world consistency. If repairable, return a complete revised "
                "proposal. Do not reward mere schema compliance."
            ),
            prompt=f"PROPOSAL:\n{_json(proposal)}\nCHAPTER:\n{_json(chapter)}\nEND:\n{_json(end)}\nRECENT:\n{_json(self.state.recent())}\nRELATED:\n{_json(related)}",
            schema=PlotNodeReview,
        )

    def plan(self, outline: StoryOutlineArtifact, anchors: ChapterAnchorsArtifact,
             blueprint: NarrativeBlueprint) -> tuple[IncrementalStorylineArtifact, NodeReviewHistory]:
        self.state = StorylineState(outline.chapters)
        by_chapter = {x.chapter_id: x for x in anchors.anchors}
        global_order = 1
        previous: PlotNode | None = None
        for chapter in outline.chapters:
            anchor = by_chapter[chapter.id]
            budget = self.cpn_budget(chapter)
            per_node_words = chapter.target_words // (budget + 2)
            begin_proposal = PlotNodeProposal(subject=anchor.begin_subject, verb=anchor.begin_verb,
                object=anchor.begin_object, purpose="Establish chapter state", schema_beat_id="chapter_begin",
                preconditions=["previous chapter state"], effects=["chapter initial state established"],
                intention="Continue the active character goal", conflict="The central opposition remains active")
            begin = self._node(begin_proposal, chapter, "CBN", global_order, 1, per_node_words)
            links = [] if previous is None else [NarrativeEdge(source=previous.id, target=begin.id,
                relation="enables", strength=5, rationale="The previous chapter state enables this beginning")]
            self.state.accept(begin, links); self.nekg.apply(begin); previous = begin; global_order += 1
            for slot in range(1, budget + 1):
                revision = ""
                for attempt in range(1, self.max_retries + 2):
                    proposal = self._proposal(chapter, anchor, blueprint, revision, slot, budget)
                    review = self._review(proposal, chapter, anchor)
                    candidate = review.revised if review.revised is not None else proposal
                    if review.accepted:
                        node = self._node(candidate, chapter, "CPN", global_order, slot + 1, per_node_words)
                        link = NarrativeEdge(source=previous.id, target=node.id, relation="causes", strength=5,
                            rationale=f"Effects of {previous.id} satisfy or motivate the next event")
                        self.state.accept(node, [link]); self.nekg.apply(node, candidate.state_changes)
                        self.history.records.append(AcceptedNodeRecord(node=node, state_changes=candidate.state_changes,
                                                                      review=review, attempt=attempt))
                        previous = node; global_order += 1
                        break
                    self.history.rejected.append({"chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                                                  "proposal": proposal.model_dump(mode="json"), "issues": review.issues})
                    revision = "; ".join(review.issues)
                else:
                    raise ValueError(f"CPN {chapter.id}:{slot} failed after {self.max_retries + 1} attempts")
            end_proposal = PlotNodeProposal(subject=anchor.end_subject, verb=anchor.end_verb,
                object=anchor.end_object, purpose="Pay off the chapter question", schema_beat_id="chapter_end",
                preconditions=["chapter CPN consequences"], effects=["chapter end state established"],
                intention="Resolve or transform the active chapter goal", conflict="The outcome has a meaningful cost")
            remainder = chapter.target_words - per_node_words * (budget + 1)
            end = self._node(end_proposal, chapter, "CEN", global_order, budget + 2, max(1, remainder))
            self.state.accept(end, [NarrativeEdge(source=previous.id, target=end.id, relation="causes", strength=5,
                rationale="Accepted CPN consequences produce the chapter ending")])
            self.nekg.apply(end); previous = end; global_order += 1
        return self.state.artifact(), self.history
