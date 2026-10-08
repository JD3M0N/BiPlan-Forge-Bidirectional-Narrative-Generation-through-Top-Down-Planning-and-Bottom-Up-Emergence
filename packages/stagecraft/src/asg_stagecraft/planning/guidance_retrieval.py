"""Retrieve narrative possibilities by meaning, retaining lexical evidence only for diagnostics."""

import json

from ..runtime.provider import LanguageModelProvider
from ..schemas import StoryRequest
from .catalog import CATALOG_HASH, CATALOG_VERSION, PLOT_SKELETONS, SKELETONS_BY_ID
from .guidance_calls import request_validated
from .guidance_models import RetrievalArtifact, RetrievalCandidate, RetrievalDraft
from .skeleton_match import lexical_scores

RETRIEVAL_INSTRUCTION = (
    "Read the underlying dramatic possibilities of this structured request against EVERY catalog "
    "entry. Return every skeleton_id exactly once. Rate relevance independently from 0 to 1. "
    "Mark pertinent when its dramatic tension helps this premise, weak for a speculative fit, "
    "or incompatible ONLY when it conflicts with an explicit constraint. Incompatible entries "
    "must cite zero-based constraint_indices; other entries must leave that list empty. "
    "Negated elements are not positive evidence: 'no romance' must not promote love. "
    "Creative directions are inferred possibilities, not requirements. Explain each judgment "
    "briefly using the request. Layers describe typical uses, not permitted uses. Return English."
)


def validate_retrieval(draft: RetrievalDraft, request: StoryRequest) -> None:
    """Reject missing judgments, duplicate IDs and unsupported incompatibility references."""
    ids = [row.skeleton_id for row in draft.judgments]
    issues = []
    missing = sorted(set(SKELETONS_BY_ID) - set(ids))
    unknown = sorted(set(ids) - set(SKELETONS_BY_ID))
    duplicates = sorted({key for key in ids if ids.count(key) > 1})
    if missing or unknown or duplicates:
        issues.append(
            f"judgments: return every catalog id once; missing={missing}, "
            f"unknown={unknown}, duplicates={duplicates}"
        )
    for row in draft.judgments:
        indices = row.constraint_indices
        prefix = f"{row.skeleton_id}.constraint_indices"
        if len(indices) != len(set(indices)):
            issues.append(f"{prefix}: remove duplicate indices")
        if any(index < 0 or index >= len(request.constraints) for index in indices):
            issues.append(f"{prefix}: use existing zero-based explicit constraint positions only")
        if row.status == "incompatible" and not indices:
            issues.append(
                f"{prefix}: incompatible requires at least one explicit conflicting "
                f"constraint; if none exists, reassess as weak or pertinent"
            )
        elif row.status != "incompatible" and indices:
            issues.append(
                f"{prefix}: {row.status} requires an empty list; clear supporting "
                f"references, or reassess status if a conflict exists"
            )
    if issues:
        raise ValueError("\n".join(issues))


def retrieve_patterns(request: StoryRequest, provider: LanguageModelProvider) -> RetrievalArtifact:
    """Recover at most ten patterns and persist enough evidence to audit any degradation."""
    query = "\n".join(
        value for value in (request.processed_prompt, request.premise, request.title) if value
    )
    lexical = {row.skeleton_id: row for row in lexical_scores(query)}
    prompt = json.dumps(
        {
            "request": request.agent_spec(),
            "indexed_constraints": [
                {"index": i, "text": value} for i, value in enumerate(request.constraints)
            ],
            "catalog": [entry.catalog_entry() for entry in PLOT_SKELETONS],
        },
        ensure_ascii=False,
        indent=2,
    )

    def validate(draft: RetrievalDraft) -> None:
        """Check response references against this request and the complete catalog."""
        validate_retrieval(draft, request)

    rejected_drafts: list[dict] = []
    draft, diagnostics, attempts = request_validated(
        provider,
        instruction=RETRIEVAL_INSTRUCTION,
        prompt=prompt,
        schema=RetrievalDraft,
        validate=validate,
        profile="extraction",
        rejected_drafts=rejected_drafts,
    )
    if draft is None:
        candidates = []
    else:
        candidates = [
            RetrievalCandidate(
                **row.model_dump(),
                lexical_score=lexical[row.skeleton_id].lexical_score,
                matched_terms=lexical[row.skeleton_id].matched_terms,
            )
            for row in draft.judgments
            if row.status == "pertinent"
        ]
        if not candidates:
            candidates = [
                RetrievalCandidate(
                    **row.model_dump(),
                    lexical_score=lexical[row.skeleton_id].lexical_score,
                    matched_terms=lexical[row.skeleton_id].matched_terms,
                )
                for row in draft.judgments
                if row.status == "weak"
            ]
        candidates.sort(
            key=lambda row: (
                -row.relevance,
                lexical[row.skeleton_id].catalog_order,
            )
        )
    return RetrievalArtifact(
        catalog_version=CATALOG_VERSION,
        catalog_hash=CATALOG_HASH,
        catalog_snapshot=list(PLOT_SKELETONS),
        request=request.agent_spec(),
        judgments=draft.judgments if draft else [],
        candidates=candidates[:10],
        degraded=draft is None,
        diagnostics=diagnostics,
        attempts=attempts,
        rejected_drafts=rejected_drafts,
    )
