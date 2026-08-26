"""Small, transactional pseudo-CPN generation and review loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from collections.abc import Callable

from pydantic import BaseModel, Field

from ..domain import (
    ChapterPlan, StoryFrame, StorylineCast, TaxonomyApplication, TaxonomyBrief,
    WorldArtifact,
)
from ..errors import StructuredResponseError
from .dependency import CpnValidator, DependencyIssue, DependencyReport
from .graph import NarrativeGraphBackend
from .models import (
    ChapterAnchors, PlotNode, PlotNodeProposal, PlotNodeReview, StoryStateSnapshot,
)
from .reviewer import DramaticReviewer


def _json(value) -> str:
    def convert(item):
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, dict):
            return {key: convert(child) for key, child in item.items()}
        if isinstance(item, (list, tuple, set, frozenset)):
            return [convert(child) for child in item]
        return item
    return json.dumps(convert(value), ensure_ascii=False, indent=2)


def _palette(brief: TaxonomyBrief | None) -> dict | None:
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


@dataclass(frozen=True)
class CpnContext:
    """Everything needed to create one CPN slot, without mutable planner state."""

    chapter: ChapterPlan
    anchor: ChapterAnchors
    world: WorldArtifact
    characters: StorylineCast
    story_frame: StoryFrame
    chapter_cpns: tuple[PlotNode, ...]
    recent_nodes: tuple[PlotNode, ...]
    snapshot: StoryStateSnapshot
    accepted_node_ids: frozenset[str]
    forbidden_svos: frozenset[tuple[str, str, str]]
    location_bridge: dict
    slot: int
    minimum: int
    maximum: int
    taxonomy_brief: TaxonomyBrief | None = None
    taxonomy_application: TaxonomyApplication | None = None


class CpnAttemptResult(BaseModel):
    """Observable outcome of one Gemini proposal/review attempt."""

    attempt: int
    stage: str
    accepted: bool = False
    proposal: PlotNodeProposal | None = None
    candidate: PlotNodeProposal | None = None
    review: PlotNodeReview | None = None
    issues: list[DependencyIssue] = Field(default_factory=list)
    validation: dict | None = None


class CpnAttemptsExhausted(Exception):
    def __init__(self, context: CpnContext, attempts: list[CpnAttemptResult]) -> None:
        super().__init__(f"CPN attempts exhausted for {context.chapter.id}:{context.slot}")
        self.context = context
        self.attempts = attempts


class CpnPlanner:
    """Generate a pseudo-CPN, review it, and return only a fully valid candidate."""

    def __init__(
        self,
        provider,
        validator: CpnValidator,
        *,
        max_retries: int,
        reviewer: DramaticReviewer | None = None,
        emit: Callable[..., None] | None = None,
        reject: Callable[[dict], None] | None = None,
    ) -> None:
        self.provider = provider
        self.validator = validator
        self.max_retries = max_retries
        self.reviewer = reviewer or DramaticReviewer(provider)
        self.emit = emit
        self.reject = reject

    def _emit(self, kind: str, message: str, context: CpnContext, attempt: int) -> None:
        if self.emit:
            self.emit(
                kind, message, chapter_id=context.chapter.id, attempt=attempt,
            )

    @staticmethod
    def _repair_hint(code: str) -> str:
        return {
            "CHARACTER_ABSENT": "Use the character's current location or move them adjacently.",
            "OBJECT_ABSENT": "Use an object present at the event location.",
            "OBJECT_UNAVAILABLE": "Use an available object or its current owner as participant.",
            "FALSE_PRECONDITION": "Remove the false predicate or first establish it in an earlier event.",
            "ILLEGAL_MOVEMENT": "Move through one adjacent location only.",
            "NO_OP_EFFECT": "Produce a new observable state value.",
            "CEN_EFFECT_RESERVED": "Create an intermediate change; leave the exact CEN effect untouched.",
            "REQUIRED_LOCATION_BRIDGE": "Move the ending subject to required_next_location now.",
            "UNREACHABLE_CEN_LOCATION": "The chapter anchors must be regenerated with a reachable ending.",
            "DUPLICATE_SVO": "Use a different subject-verb-object event.",
            "INVALID_TAXONOMY_REFERENCE": "Use one supplied movement pair or leave both taxonomy fields empty.",
            "EARLY_CEN_ALIGNMENT": "Continue development and keep aligns_with_cen false.",
            "FINAL_CEN_ALIGNMENT": "Make the CEN possible as the immediate next event.",
            "STRUCTURED_RESPONSE": "Return a complete object matching the required schema.",
            "REVIEW_REJECTED": "Repair every dramatic review issue without violating factual state.",
        }.get(code, "Return a different candidate that resolves this issue.")

    def _feedback(
        self,
        issues: list[DependencyIssue],
        previous: PlotNodeProposal | None,
        repeated_codes: bool,
    ) -> str:
        payload: dict = {
            "issues": [
                {
                    "code": item.code,
                    "message": item.message,
                    "required_correction": self._repair_hint(item.code),
                }
                for item in issues
            ],
        }
        if repeated_codes and previous is not None:
            payload["repeated_failure"] = (
                "The previous repair repeated the same validation class. Change the causal action, "
                "not only its wording. Do not reuse the SVO or exact effects below."
            )
            payload["must_not_reuse"] = {
                "svo": [previous.subject.id, previous.verb, previous.object.id],
                "effects": previous.effects,
            }
        return _json(payload)

    def _propose(
        self,
        context: CpnContext,
        feedback: str,
        previous: PlotNodeProposal | None,
        attempt: int,
    ) -> PlotNodeProposal:
        ending_rule = (
            "The event may bridge immediately to the ending because the minimum development exists."
            if context.slot >= context.minimum else
            "The event must develop the conflict and must not bridge immediately to the ending yet."
        )
        if context.slot == context.maximum:
            ending_rule = "This final allowed event must create an immediate factual bridge to the ending."
        repair_rule = (
            "Rewrite and repair the previous candidate using every structured issue below. "
            if feedback else ""
        )
        self._emit(
            "agent_called", "se llamo al agente plot_node_proposal", context, attempt,
        )
        return self.provider.generate_structured(
            system_instruction=(
                f"{repair_rule}Generate one concrete SVO internal plot event. Use canonical supplied "
                "entity and location IDs, explicit dependencies on accepted node IDs, typed factual "
                "preconditions, and typed state mutations. The event must follow character intention, "
                "meet active opposition, change state, avoid repetition, and advance toward the chapter "
                f"ending. {ending_rule} Taxonomy is a flexible palette, never a checklist. An object can "
                "only participate where its current state says it is located or owned. A movement event "
                "happens at the actor's current source location; represent the adjacent destination only "
                "as a location effect. If REQUIRED LOCATION BRIDGE says must_move_now, move its subject "
                "to required_next_location. Never repeat a forbidden SVO. Return internal text in English."
            ),
            prompt=(
                f"CHAPTER:\n{_json(context.chapter)}\n\nBEGIN ANCHOR:\n{_json(context.anchor)}"
                f"\n\nEND TARGET:\n{_json({'subject': context.anchor.end_subject, 'verb': context.anchor.end_verb, 'object': context.anchor.end_object, 'location_id': context.anchor.end_location_id})}"
                f"\n\nCEN TARGET STATE:\n{_json({'preconditions': context.anchor.end_preconditions, 'effects': context.anchor.end_effects})}"
                "\nDo not perform an exact CEN effect early. CEN preconditions are targets for the "
                "state immediately before the CEN; intermediate values may evolve."
                f"\n\nSLOT: {context.slot}/{context.maximum}; MINIMUM: {context.minimum}"
                f"\n\nSTORY FRAME:\n{_json(context.story_frame)}"
                f"\n\nWORLD RULES AND MAP:\n{_json(context.world)}"
                f"\n\nCHARACTER FACTS:\n{_json(context.characters)}"
                f"\n\nRECENT ACCEPTED EVENTS:\n{_json(context.recent_nodes)}"
                f"\n\nACCEPTED CHAPTER EVENTS:\n{_json(context.chapter_cpns)}"
                f"\n\nCURRENT ENTITY STATE (AUTHORITATIVE):\n{_json(context.snapshot)}"
                f"\n\nREQUIRED LOCATION BRIDGE:\n{_json(context.location_bridge)}"
                f"\n\nALLOWED DEPENDENCY IDS:\n{_json(context.accepted_node_ids)}"
                f"\n\nFORBIDDEN SVO SIGNATURES:\n{_json(context.forbidden_svos)}"
                f"\n\nNARRATIVE PALETTE:\n{_json(_palette(context.taxonomy_brief))}"
                f"\n\nSELECTED MOVEMENT REFERENCES:\n{_json(context.taxonomy_application.selected_movements) if context.taxonomy_application else 'none'}"
                f"\n\nPREVIOUS REJECTED PROPOSAL:\n{_json(previous) if previous else 'none'}"
                f"\n\nSTRUCTURED REPAIR FEEDBACK:\n{feedback or 'none'}"
            ),
            schema=PlotNodeProposal,
        )

    def _record_rejection(
        self, context: CpnContext, result: CpnAttemptResult,
    ) -> None:
        record = {
            "chapter_id": context.chapter.id,
            "slot": context.slot,
            "attempt": result.attempt,
            "stage": result.stage,
            "issues": [item.message for item in result.issues],
            "issue_codes": [item.code for item in result.issues],
        }
        if result.proposal is not None:
            record["proposal"] = result.proposal.model_dump(mode="json")
        if result.stage == "dependency":
            record["validation_codes"] = [item.code for item in result.issues]
        if result.validation is not None:
            record["validation"] = result.validation
        if result.review is not None:
            record["review"] = result.review.model_dump(mode="json")
        if result.candidate is not None:
            record["candidate"] = result.candidate.model_dump(mode="json")
        if self.reject:
            self.reject(record)

    def _validate(self, proposal: PlotNodeProposal, context: CpnContext) -> DependencyReport:
        return self.validator.validate(
            proposal,
            context.snapshot,
            set(context.accepted_node_ids),
            anchor=context.anchor,
            forbidden_svos=set(context.forbidden_svos),
            location_bridge=context.location_bridge,
            taxonomy_application=context.taxonomy_application,
        )

    def plan_slot(
        self,
        context: CpnContext,
        graph: NarrativeGraphBackend,
        *,
        attempt_offset: int = 0,
    ) -> CpnAttemptResult:
        attempts: list[CpnAttemptResult] = []
        feedback = ""
        previous: PlotNodeProposal | None = None
        previous_codes: tuple[str, ...] = ()

        for local_attempt in range(1, self.max_retries + 2):
            attempt = attempt_offset + local_attempt
            try:
                proposal = self._propose(context, feedback, previous, attempt)
            except StructuredResponseError as exc:
                issue = DependencyIssue(
                    code="STRUCTURED_RESPONSE",
                    message="The candidate response was structurally invalid. Return a complete valid replacement.",
                )
                result = CpnAttemptResult(
                    attempt=attempt, stage="proposal", issues=[issue],
                    validation={
                        "error_code": exc.code, "error_stage": exc.stage,
                        "details": exc.details,
                    },
                )
                attempts.append(result)
                self._record_rejection(context, result)
                feedback = self._feedback([issue], previous, previous_codes == (issue.code,))
                previous_codes = (issue.code,)
                continue

            if self.validator.normalize_movement_origin(proposal, context.snapshot):
                self._emit(
                    "movement_normalized",
                    f"movimiento de {proposal.subject.id}: evento ubicado en origen {proposal.location_id}",
                    context, attempt,
                )
            if self.validator.normalize_taxonomy_reference(
                proposal, context.taxonomy_application,
            ):
                self._emit(
                    "taxonomy_normalized",
                    "referencia taxonomica CPN invalida eliminada; la paleta es opcional",
                    context, attempt,
                )
            deterministic = self._validate(proposal, context)
            if not deterministic.passed:
                codes = tuple(item.code for item in deterministic.issues)
                result = CpnAttemptResult(
                    attempt=attempt, stage="dependency", proposal=proposal,
                    candidate=proposal, issues=deterministic.issues,
                )
                attempts.append(result)
                self._record_rejection(context, result)
                feedback = self._feedback(deterministic.issues, proposal, codes == previous_codes)
                previous, previous_codes = proposal, codes
                continue

            try:
                self._emit(
                    "agent_called", "se llamo al agente dramatic_reviewer", context, attempt,
                )
                review = self.reviewer.review(
                    proposal, context.chapter, context.anchor, context.world,
                    context.characters, deterministic, list(context.recent_nodes), graph,
                    alignment_allowed=context.slot >= context.minimum,
                )
            except StructuredResponseError as exc:
                issue = DependencyIssue(
                    code="STRUCTURED_RESPONSE",
                    message="The review response was structurally invalid. Return a complete valid replacement.",
                )
                result = CpnAttemptResult(
                    attempt=attempt, stage="review", proposal=proposal, issues=[issue],
                    validation={
                        "error_code": exc.code, "error_stage": exc.stage,
                        "details": exc.details,
                    },
                )
                attempts.append(result)
                self._record_rejection(context, result)
                feedback = self._feedback([issue], proposal, previous_codes == (issue.code,))
                previous, previous_codes = proposal, (issue.code,)
                continue

            if context.slot < context.minimum:
                alignment_only = [
                    issue for issue in review.issues
                    if "aligns_with_cen" in issue.casefold()
                    or ("minimum" in issue.casefold() and "chapter" in issue.casefold())
                ]
                normalized = review.aligns_with_cen
                review.aligns_with_cen = False
                checks = (
                    review.causal, review.intentional, review.conflict_present,
                    review.continuous, review.novel, review.advances_ending,
                    review.world_consistent, review.emotionally_effective,
                )
                if (not review.accepted and review.issues
                        and len(alignment_only) == len(review.issues) and all(checks)):
                    review.accepted = True
                    review.issues = []
                    normalized = True
                if normalized:
                    self._emit(
                        "review_normalized",
                        f"CPN {context.chapter.id}:{context.slot}: alineacion aplazada hasta el minimo",
                        context, attempt,
                    )

            candidate = review.revised or proposal
            if self.validator.normalize_movement_origin(candidate, context.snapshot):
                self._emit(
                    "movement_normalized",
                    f"movimiento de {candidate.subject.id}: evento ubicado en origen {candidate.location_id}",
                    context, attempt,
                )
            if self.validator.normalize_taxonomy_reference(
                candidate, context.taxonomy_application,
            ):
                self._emit(
                    "taxonomy_normalized",
                    "referencia taxonomica del reemplazo eliminada; la paleta es opcional",
                    context, attempt,
                )
            post = self._validate(candidate, context)
            ready_for_cen = self.validator.cen_ready(
                candidate, context.snapshot, context.anchor,
            )
            if context.slot >= context.minimum:
                review.aligns_with_cen = ready_for_cen
            if review.revised is not None and post.passed:
                review.accepted = True
                review.issues = []
                self._emit(
                    "review_replacement_accepted",
                    "reemplazo del revisor aceptado tras revalidacion determinista",
                    context, attempt,
                )
            issues = list(post.issues)
            if not review.accepted:
                issues.extend(
                    DependencyIssue(code="REVIEW_REJECTED", message=message)
                    for message in review.issues
                )
            if review.aligns_with_cen and context.slot < context.minimum:
                issues.append(DependencyIssue(
                    code="EARLY_CEN_ALIGNMENT",
                    message="minimum chapter development has not been reached",
                ))
            if context.slot == context.maximum and not review.aligns_with_cen:
                issues.append(DependencyIssue(
                    code="FINAL_CEN_ALIGNMENT",
                    message="final candidate does not bridge immediately to the ending",
                ))

            if review.accepted and not issues:
                return CpnAttemptResult(
                    attempt=attempt, stage="accepted", accepted=True,
                    proposal=proposal, candidate=candidate, review=review,
                )

            codes = tuple(item.code for item in issues)
            result = CpnAttemptResult(
                attempt=attempt, stage="review", proposal=proposal,
                candidate=candidate, review=review, issues=issues,
            )
            attempts.append(result)
            self._record_rejection(context, result)
            feedback = self._feedback(issues, candidate, codes == previous_codes)
            previous, previous_codes = candidate, codes

        raise CpnAttemptsExhausted(context, attempts)


__all__ = ["CpnAttemptResult", "CpnAttemptsExhausted", "CpnContext", "CpnPlanner"]
