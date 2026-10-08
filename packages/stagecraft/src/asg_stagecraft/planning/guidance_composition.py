"""Compose retrieved patterns into premise-specific inspiration with contextual validation."""

import json
from collections import Counter

from ..runtime.provider import LanguageModelProvider
from ..schemas import StoryRequest
from .catalog_types import FunctionalRole
from .guidance_calls import request_validated
from .guidance_models import (
    CompositionArtifact,
    CompositionDraft,
    CompositionFailure,
    RetrievalArtifact,
)
from .guidance_render import render_blocks
from .profiles import NarrativeProfile, profile_guidance

COMPOSITION_INSTRUCTION = (
    "Compose optional narrative inspiration from the retrieved candidates. Recheck every choice "
    "against explicit requirements, especially negations: lexical-only candidates are unverified. "
    "Choose at most one principal pattern. A pattern's catalog layers are typical uses, never "
    "restrictions: reunion or heist may carry a whole story. Secondary means a developed line; "
    "local means a situation or turn, not an extra subplot. Each selection needs premise evidence "
    "and a concrete contribution. Fill the connection field for EVERY selection: state how a "
    "principal pattern organizes the conflict and how secondary/local patterns causally affect it. "
    "Essential permits no secondary lines and at most one local choice. Developed permits at "
    "most one secondary and one local choice. Expansive permits at most three additional choices. "
    "These are ceilings, never quotas. Abstain with a reason and empty selections, suggestions, "
    "questions and movements and null deviation if no pattern helps. Otherwise select at least one "
    "pattern; a principal is optional for a story that only benefits from a local resource. "
    "Adapt at most two source pressure_questions and two possible_movements total; cite their "
    "skeleton_id and zero-based source_index. Directed pairs_well_with and tensions_with are "
    "editorial suggestions, not rules. Suggest character functions only for warranted characters, "
    "with open everyday persona vocabulary. A deviation is optional; explain its premise_basis "
    "and convention, never change an explicitly requested fact or ending. Be concise and specific. "
    "Return English."
)


def validate_composition(
    draft: CompositionDraft, request: StoryRequest, retrieval: RetrievalArtifact
) -> None:
    """Enforce references and complexity without treating typical catalog layers as permissions."""
    if draft.abstained:
        if any(
            (
                draft.selections,
                draft.role_suggestions,
                draft.questions,
                draft.movements,
                draft.deviation,
            )
        ):
            raise ValueError("abstention must contain no narrative guidance")
        return
    ids = [choice.skeleton_id for choice in draft.selections]
    candidates = {row.skeleton_id for row in retrieval.candidates}
    if not ids or len(ids) != len(set(ids)) or not set(ids) <= candidates:
        raise ValueError("select unique existing candidate ids or abstain")
    counts = Counter(choice.scope for choice in draft.selections)
    if counts["principal"] > 1:
        raise ValueError("at most one principal pattern is allowed")
    _validate_scope_counts(counts, request.narrative_profile)
    for index, choice in enumerate(draft.selections):
        if choice.scope != "principal" and not choice.connection.strip():
            raise ValueError(
                f"selections[{index}].connection ({choice.skeleton_id}) must explain how this "
                "secondary/local contribution causally affects the central conflict"
            )
    entries = {entry.id: entry for entry in retrieval.catalog_snapshot}
    for field, suggestions in (
        ("pressure_questions", draft.questions),
        ("possible_movements", draft.movements),
    ):
        references = [(row.skeleton_id, row.source_index) for row in suggestions]
        if len(references) != len(set(references)):
            raise ValueError("adapted source references must be unique within each category")
        for row in suggestions:
            if row.skeleton_id not in ids or row.source_index >= len(
                getattr(entries[row.skeleton_id], field)
            ):
                raise ValueError("adaptations must cite an existing item in a selected pattern")


def _validate_scope_counts(counts: Counter, profile: NarrativeProfile) -> None:
    """Apply profile-specific ceilings without requiring additional narrative lines."""
    if profile == NarrativeProfile.ESSENTIAL and (counts["secondary"] or counts["local"] > 1):
        raise ValueError("essential permits no secondary pattern and at most one local pattern")
    if profile == NarrativeProfile.DEVELOPED and (counts["secondary"] > 1 or counts["local"] > 1):
        raise ValueError("developed permits at most one secondary and one local pattern")
    if profile == NarrativeProfile.EXPANSIVE and counts["secondary"] + counts["local"] > 3:
        raise ValueError("expansive permits at most three non-principal patterns")


def compose_patterns(
    request: StoryRequest, retrieval: RetrievalArtifact, provider: LanguageModelProvider
) -> CompositionArtifact | CompositionFailure:
    """Compose once with one repair, freezing the source entries and exact downstream blocks."""
    if retrieval.degraded or not retrieval.candidates:
        reason = "retrieval_failed" if retrieval.degraded else "no_eligible_candidates"
        return CompositionArtifact(
            abstained=True,
            reason=reason,
            catalog_version=retrieval.catalog_version,
            catalog_hash=retrieval.catalog_hash,
            catalog_snapshot=[],
            diagnostics=list(retrieval.diagnostics),
            attempts=0,
        )
    entries = {entry.id: entry for entry in retrieval.catalog_snapshot}
    shortlist = []
    for candidate in retrieval.candidates:
        entry = entries[candidate.skeleton_id]
        shortlist.append(
            {
                "judgment": candidate.model_dump(),
                "pattern": entry.model_dump(mode="json", exclude={"influences"}),
            }
        )
    prompt = json.dumps(
        {
            "request": request.agent_spec(),
            "profile_contract": profile_guidance(request.narrative_profile),
            "retrieval_degraded": retrieval.degraded,
            "candidates": shortlist,
            "functional_roles": [role.value for role in FunctionalRole],
        },
        ensure_ascii=False,
        indent=2,
    )

    def validate(draft: CompositionDraft) -> None:
        """Validate selections against this request and the recorded shortlist."""
        validate_composition(draft, request, retrieval)

    draft, diagnostics, attempts = request_validated(
        provider,
        instruction=COMPOSITION_INSTRUCTION,
        prompt=prompt,
        schema=CompositionDraft,
        validate=validate,
        profile="planning",
    )
    if draft is None:
        return CompositionFailure(diagnostics=diagnostics)
    character_block, planning_block = render_blocks(draft)
    return CompositionArtifact(
        **draft.model_dump(),
        catalog_version=retrieval.catalog_version,
        catalog_hash=retrieval.catalog_hash,
        catalog_snapshot=[entries[choice.skeleton_id] for choice in draft.selections],
        character_block=character_block,
        planning_block=planning_block,
        diagnostics=diagnostics,
        attempts=attempts,
    )
