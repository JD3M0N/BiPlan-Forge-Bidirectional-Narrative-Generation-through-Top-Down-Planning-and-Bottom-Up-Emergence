"""Incremental CPN planner with live STORYLINE and NEKG feedback."""

from __future__ import annotations

import json
import math

from pydantic import BaseModel, Field

from .craft import validate_craft_outline, validate_storyline_craft
from .errors import StorylinePlanningError, StructuredResponseError
from .nekg import NarrativeEntityGraph
from .narrative_db import NarrativeBlueprint
from .schemas import (
    AcceptedNodeRecord, ChapterAnchorsArtifact, ChapterPlan, CharactersArtifact,
    CraftContractArtifact, IncrementalStorylineArtifact, NarrativeEdge, NodeGoal,
    PlotNode, PlotNodeProposal, PlotNodeReview, StoryOutlineArtifact,
    StoryPlanArtifact, StoryRequest, WorldArtifact,
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

    def _checkpoint(self, callback) -> None:
        if callback is not None:
            callback(self.state.artifact(), self.nekg.artifact(), self.history)

    @staticmethod
    def _structured_rejection(exc: StructuredResponseError, stage: str) -> tuple[str, dict]:
        schema = str(exc.details.get("schema", "structured response"))
        attempts = int(exc.details.get("attempts", 1))
        issue = f"Invalid {schema} after {attempts} structured attempts during {stage}"
        return issue, {
            "stage": stage,
            "schema": schema,
            "structured_attempts": attempts,
            "validation_errors": exc.details.get("validation_errors", []),
        }

    def outline(self, request: StoryRequest, plan: StoryPlanArtifact,
                blueprint: NarrativeBlueprint, craft: CraftContractArtifact | None = None,
                characters: CharactersArtifact | None = None) -> StoryOutlineArtifact:
        craft_instruction = ""
        craft_context = ""
        if craft is not None and characters is not None:
            craft_instruction = (
                " Assign every craft promise exactly one setup, one or more progress beats, and one "
                "payoff in that order. Give every main character exactly three focus-slider milestones "
                "(start, transition, end). Distribute exactly the required number of try-fail cycles, "
                "each as Yes-but or No-and with a persistent consequence."
            )
            craft_context = f"\nCHARACTERS:\n{_json(characters)}\nCRAFT CONTRACT:\n{_json(craft)}"
        outline = self.provider.generate_structured(
            system_instruction=(
                "Create the high-level STORYTELLER frame. Produce a premise, a complete synopsis, "
                "and ordered chapter abstracts before creating plot nodes. Allocate exactly the "
                "requested total words. Use retrieved narrative knowledge as flexible design guidance, "
                "never as literal prose. Ensure escalation, a consequential climax, and enough "
                f"aftermath.{craft_instruction}"
            ),
            prompt=(f"REQUEST:\n{_json(request)}\nPLAN:\n{_json(plan)}"
                    f"{craft_context}"
                    f"\nRETRIEVED KNOWLEDGE:\n{_json(blueprint)}"),
            schema=StoryOutlineArtifact,
        )
        if craft is not None and characters is not None:
            validate_craft_outline(outline, craft, characters)
        return outline

    def anchors(self, outline: StoryOutlineArtifact, world: WorldArtifact,
                characters: CharactersArtifact) -> ChapterAnchorsArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Generate exactly one SVO begin anchor and one SVO end anchor for every chapter. "
                "Consider the preceding and following chapter abstracts so adjacent states connect. "
                "The begin event must concretely embody setup and start beats assigned to the chapter; "
                "the end event must embody payoff and end beats. Anchors describe observable events, "
                "not scores, themes, IDs, or narration instructions."
            ),
            prompt=f"OUTLINE:\n{_json(outline)}\nWORLD:\n{_json(world)}\nCHARACTERS:\n{_json(characters)}",
            schema=ChapterAnchorsArtifact,
        )

    @staticmethod
    def cpn_budget(chapter: ChapterPlan) -> int:
        # Short chapters benefit from fewer, better-developed events.
        return max(1, min(6, math.ceil(chapter.target_words / 450)))

    def _node(self, proposal: PlotNodeProposal, chapter: ChapterPlan, kind: str,
              global_order: int, local_order: int, target_words: int,
              *, craft_beat_ids: list[str] | None = None,
              character_milestone_ids: list[str] | None = None,
              try_fail_cycle_ids: list[str] | None = None) -> PlotNode:
        cycle_ids = try_fail_cycle_ids if try_fail_cycle_ids is not None else proposal.try_fail_cycle_ids
        cycle_by_id = {cycle.id: cycle for cycle in chapter.try_fail_cycles}
        effects = list(proposal.effects)
        for identifier in cycle_ids:
            consequence = cycle_by_id[identifier].consequence
            if consequence not in effects:
                effects.append(consequence)
        return PlotNode(
            id=f"n_{global_order:04d}", chapter_id=chapter.id, node_type=kind,
            subject=proposal.subject, verb=proposal.verb, object=proposal.object,
            timestamp=global_order - 1, global_order=global_order, local_order=local_order,
            target_words=max(1, target_words), preconditions=proposal.preconditions,
            effects=effects, intention=proposal.intention, conflict=proposal.conflict,
            craft_beat_ids=(craft_beat_ids if craft_beat_ids is not None else proposal.craft_beat_ids),
            character_milestone_ids=(character_milestone_ids if character_milestone_ids is not None
                                     else proposal.character_milestone_ids),
            try_fail_cycle_ids=cycle_ids, try_fail_outcome=proposal.try_fail_outcome,
            goals=[NodeGoal(purpose=proposal.purpose, archetype_id="composed",
                            taxonomy_beat=proposal.schema_beat_id,
                            success_criteria=["The event causes an observable state change"])],
        )

    def _proposal(self, chapter, end, blueprint, revision, slot, budget,
                  remaining_beats, remaining_milestones, remaining_cycles) -> PlotNodeProposal:
        recent = self.state.recent()
        return self.provider.generate_structured(
            system_instruction=(
                "Generate one pseudo-CPN as a concrete SVO event. It must be caused or enabled by "
                "accepted events, follow a character intention, meet active opposition, change story "
                "state, and move toward the chapter end without jumping there prematurely. Avoid "
                "rephrasing prior events. Cover only supplied remaining craft IDs and claim each only "
                "when the event concretely realizes it. On the final slot cover every remaining ID. "
                "A try-fail event covers at most one cycle and must use its exact Yes-but or No-and "
                "outcome; its consequence must persist in effects. Never expose craft terms in prose."
            ),
            prompt=(f"CHAPTER:\n{_json(chapter)}\nEND ANCHOR:\n{_json(end)}\nSLOT: {slot}/{budget}\n"
                    f"RECENT STORYLINE:\n{_json(recent)}\nRELATED NEKG:\n{_json(self.nekg.artifact())}\n"
                    f"REMAINING CRAFT BEATS:\n{_json(remaining_beats)}\n"
                    f"REMAINING CHARACTER MILESTONES:\n{_json(remaining_milestones)}\n"
                    f"REMAINING TRY-FAIL CYCLES:\n{_json(remaining_cycles)}\n"
                    f"BLUEPRINT:\n{_json(blueprint)}\nREVISION FEEDBACK:\n{revision or 'none'}"),
            schema=PlotNodeProposal,
        )

    def _review(self, proposal, chapter, end) -> PlotNodeReview:
        related = self.nekg.related(proposal.subject, proposal.object)
        return self.provider.generate_structured(
            system_instruction=(
                "Review one pseudo-CPN independently. Accept only if all seven checks pass: causal "
                "support, character intention, active conflict, continuity, novelty, progress toward "
                "the chapter ending, world consistency, honest craft coverage, a persistent consequence, "
                "and a valid Yes-but/No-and result when applicable. If repairable, return a complete "
                "revised proposal. Do not reward IDs or mere schema compliance."
            ),
            prompt=(f"PROPOSAL:\n{_json(proposal)}\nCHAPTER:\n{_json(chapter)}\nEND:\n{_json(end)}"
                    f"\nRECENT:\n{_json(self.state.recent())}\nRELATED:\n{_json(related)}"),
            schema=PlotNodeReview,
        )

    @staticmethod
    def _proposal_craft_issues(proposal, beats, milestones, cycles, *, remaining_slots: int) -> list[str]:
        beat_ids = {item.id for item in beats}
        milestone_ids = {item.id for item in milestones}
        cycle_by_id = {item.id: item for item in cycles}
        issues: list[str] = []
        if len(proposal.craft_beat_ids) != len(set(proposal.craft_beat_ids)):
            issues.append("The proposal repeats a craft beat ID")
        if len(proposal.character_milestone_ids) != len(set(proposal.character_milestone_ids)):
            issues.append("The proposal repeats a character milestone ID")
        if len(proposal.try_fail_cycle_ids) != len(set(proposal.try_fail_cycle_ids)):
            issues.append("The proposal repeats a try-fail cycle ID")
        if not set(proposal.craft_beat_ids) <= beat_ids:
            issues.append("The proposal claims an unavailable craft beat")
        if not set(proposal.character_milestone_ids) <= milestone_ids:
            issues.append("The proposal claims an unavailable character milestone")
        if not set(proposal.try_fail_cycle_ids) <= set(cycle_by_id):
            issues.append("The proposal claims an unavailable try-fail cycle")
        if len(proposal.try_fail_cycle_ids) > 1:
            issues.append("One event may cover at most one try-fail cycle")
        if len(cycles) >= remaining_slots and len(proposal.try_fail_cycle_ids) != 1:
            issues.append("This slot must cover one remaining try-fail cycle")
        if proposal.try_fail_cycle_ids:
            cycle = cycle_by_id.get(proposal.try_fail_cycle_ids[0])
            if cycle and proposal.try_fail_outcome != cycle.outcome:
                issues.append("The proposal does not use the planned try-fail outcome")
        elif proposal.try_fail_outcome is not None:
            issues.append("A try-fail outcome requires a cycle reference")
        if remaining_slots == 1:
            if set(proposal.craft_beat_ids) != beat_ids:
                issues.append("The final slot must cover every remaining progress beat")
            if set(proposal.character_milestone_ids) != milestone_ids:
                issues.append("The final slot must cover every remaining transition milestone")
            if set(proposal.try_fail_cycle_ids) != set(cycle_by_id):
                issues.append("The final slot must cover every remaining try-fail cycle")
        return issues

    def plan(self, outline: StoryOutlineArtifact, anchors: ChapterAnchorsArtifact,
             blueprint: NarrativeBlueprint, craft: CraftContractArtifact | None = None,
             characters: CharactersArtifact | None = None,
             on_checkpoint=None) -> tuple[IncrementalStorylineArtifact, NodeReviewHistory]:
        self.state = StorylineState(outline.chapters)
        by_chapter = {x.chapter_id: x for x in anchors.anchors}
        global_order = 1
        previous: PlotNode | None = None
        for chapter in outline.chapters:
            anchor = by_chapter[chapter.id]
            budget = max(self.cpn_budget(chapter), len(chapter.try_fail_cycles))
            per_node_words = chapter.target_words // (budget + 2)
            setup_beats = [item.id for item in chapter.craft_beats if item.kind == "setup"]
            payoff_beats = [item.id for item in chapter.craft_beats if item.kind == "payoff"]
            remaining_beats = [item for item in chapter.craft_beats if item.kind == "progress"]
            start_milestones = [item.id for item in chapter.character_milestones if item.stage == "start"]
            end_milestones = [item.id for item in chapter.character_milestones if item.stage == "end"]
            remaining_milestones = [item for item in chapter.character_milestones
                                    if item.stage == "transition"]
            remaining_cycles = list(chapter.try_fail_cycles)
            begin_proposal = PlotNodeProposal(subject=anchor.begin_subject, verb=anchor.begin_verb,
                object=anchor.begin_object, purpose="Establish chapter state", schema_beat_id="chapter_begin",
                preconditions=["previous chapter state"], effects=["chapter initial state established"],
                intention="Continue the active character goal", conflict="The central opposition remains active")
            begin = self._node(begin_proposal, chapter, "CBN", global_order, 1, per_node_words,
                               craft_beat_ids=setup_beats,
                               character_milestone_ids=start_milestones,
                               try_fail_cycle_ids=[])
            links = [] if previous is None else [NarrativeEdge(source=previous.id, target=begin.id,
                relation="enables", strength=5, rationale="The previous chapter state enables this beginning")]
            self.state.accept(begin, links); self.nekg.apply(begin); previous = begin; global_order += 1
            self._checkpoint(on_checkpoint)
            for slot in range(1, budget + 1):
                revision = ""
                for attempt in range(1, self.max_retries + 2):
                    try:
                        proposal = self._proposal(chapter, anchor, blueprint, revision, slot, budget,
                                                  remaining_beats, remaining_milestones,
                                                  remaining_cycles)
                    except StructuredResponseError as exc:
                        issue, validation = self._structured_rejection(exc, "proposal")
                        self.history.rejected.append({
                            "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                            "stage": "proposal", "proposal": None, "issues": [issue],
                            "validation": validation,
                        })
                        revision = issue
                        self._checkpoint(on_checkpoint)
                        continue
                    try:
                        review = self._review(proposal, chapter, anchor)
                    except StructuredResponseError as exc:
                        issue, validation = self._structured_rejection(exc, "review")
                        self.history.rejected.append({
                            "chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                            "stage": "review",
                            "proposal": proposal.model_dump(mode="json"),
                            "issues": [issue], "validation": validation,
                        })
                        revision = issue
                        self._checkpoint(on_checkpoint)
                        continue
                    candidate = review.revised if review.revised is not None else proposal
                    craft_issues = self._proposal_craft_issues(
                        candidate, remaining_beats, remaining_milestones, remaining_cycles,
                        remaining_slots=budget - slot + 1,
                    )
                    if review.accepted and not craft_issues:
                        node = self._node(candidate, chapter, "CPN", global_order, slot + 1, per_node_words)
                        link = NarrativeEdge(source=previous.id, target=node.id, relation="causes", strength=5,
                            rationale=f"Effects of {previous.id} satisfy or motivate the next event")
                        self.state.accept(node, [link]); self.nekg.apply(node, candidate.state_changes)
                        self.history.records.append(AcceptedNodeRecord(node=node, state_changes=candidate.state_changes,
                                                                      review=review, attempt=attempt))
                        claimed_beats = set(candidate.craft_beat_ids)
                        claimed_milestones = set(candidate.character_milestone_ids)
                        claimed_cycles = set(candidate.try_fail_cycle_ids)
                        remaining_beats = [item for item in remaining_beats if item.id not in claimed_beats]
                        remaining_milestones = [item for item in remaining_milestones
                                                if item.id not in claimed_milestones]
                        remaining_cycles = [item for item in remaining_cycles if item.id not in claimed_cycles]
                        previous = node; global_order += 1
                        self._checkpoint(on_checkpoint)
                        break
                    issues = [*review.issues, *craft_issues]
                    self.history.rejected.append({"chapter_id": chapter.id, "slot": slot, "attempt": attempt,
                                                  "proposal": proposal.model_dump(mode="json"), "issues": issues})
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
                            "Revisa planning_checkpoint/node_reviews.json o usa un modelo más capaz."
                        ],
                    )
            if remaining_beats or remaining_milestones or remaining_cycles:
                raise StorylinePlanningError(
                    f"El capítulo {chapter.id} terminó con requisitos de craft sin cubrir.",
                    details={
                        "chapter_id": chapter.id,
                        "remaining_craft_beats": [item.id for item in remaining_beats],
                        "remaining_character_milestones": [item.id for item in remaining_milestones],
                        "remaining_try_fail_cycles": [item.id for item in remaining_cycles],
                    },
                    recommendations=["Revisa el outline y los intentos CPN guardados."],
                )
            end_proposal = PlotNodeProposal(subject=anchor.end_subject, verb=anchor.end_verb,
                object=anchor.end_object, purpose="Pay off the chapter question", schema_beat_id="chapter_end",
                preconditions=["chapter CPN consequences"], effects=["chapter end state established"],
                intention="Resolve or transform the active chapter goal", conflict="The outcome has a meaningful cost")
            remainder = chapter.target_words - per_node_words * (budget + 1)
            end = self._node(end_proposal, chapter, "CEN", global_order, budget + 2, max(1, remainder),
                             craft_beat_ids=payoff_beats,
                             character_milestone_ids=end_milestones,
                             try_fail_cycle_ids=[])
            self.state.accept(end, [NarrativeEdge(source=previous.id, target=end.id, relation="causes", strength=5,
                rationale="Accepted CPN consequences produce the chapter ending")])
            self.nekg.apply(end); previous = end; global_order += 1
            self._checkpoint(on_checkpoint)
        artifact = self.state.artifact()
        if craft is not None and characters is not None:
            validate_craft_outline(outline, craft, characters)
            validate_storyline_craft(artifact, outline)
        return artifact, self.history
