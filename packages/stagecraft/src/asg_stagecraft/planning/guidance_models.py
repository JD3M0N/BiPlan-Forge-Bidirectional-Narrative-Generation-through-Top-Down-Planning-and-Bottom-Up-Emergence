"""Versioned retrieval and composition artifacts for optional narrative inspiration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .catalog_types import ID_PATTERN, FunctionalRole, PlotSkeleton


class GuidanceModel(BaseModel):
    """Reject undeclared fields in new guidance contracts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RelevanceJudgment(GuidanceModel):
    """Record relevance separately from conflict with explicit requirements."""

    skeleton_id: str = Field(pattern=ID_PATTERN)
    relevance: float = Field(ge=0, le=1)
    status: Literal["pertinent", "weak", "incompatible"]
    evidence: str = Field(min_length=1)
    # Zero-based indices into StoryRequest.constraints, never inferred directions.
    constraint_indices: list[int] = Field(
        default_factory=list,
        description=(
            "Zero-based explicit constraint indices. REQUIRED nonempty for "
            "incompatible; MUST be empty for pertinent or weak. Never cite "
            "creative directions."
        ),
    )


class RetrievalDraft(GuidanceModel):
    """Require one contextual judgment for every entry of the catalog."""

    judgments: list[RelevanceJudgment]


class RetrievalCandidate(RelevanceJudgment):
    """Add local lexical evidence without mixing incomparable score magnitudes."""

    lexical_score: float = Field(ge=0, le=1)
    matched_terms: list[str] = Field(default_factory=list)


class RetrievalArtifact(GuidanceModel):
    """Preserve the inputs, judgments and selected candidates of retrieval."""

    contract_version: Literal[2] = 2
    strategy: Literal["compositional_v2"] = "compositional_v2"
    catalog_version: str
    catalog_hash: str
    catalog_snapshot: list[PlotSkeleton]
    request: dict
    judgments: list[RelevanceJudgment] = Field(default_factory=list)
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    degraded: bool = False
    diagnostics: list[str] = Field(default_factory=list)
    attempts: int = 0
    rejected_drafts: list[dict] = Field(default_factory=list)


class PatternSelection(GuidanceModel):
    """Describe the contribution of a pattern at its request-specific scope."""

    skeleton_id: str = Field(pattern=ID_PATTERN)
    scope: Literal["principal", "secondary", "local"]
    evidence: str = Field(min_length=1)
    contribution: str = Field(min_length=1)
    connection: str = ""


class PatternSelectionDraft(PatternSelection):
    """Require an explicit causal connection in new model responses, including principal choices."""

    connection: str = Field(
        min_length=1,
        description=(
            "Explain how this selection changes the central conflict. For a principal pattern, "
            "state how it organizes that conflict; for secondary/local patterns, explain their "
            "causal effect on it. Always provide a nonempty sentence."
        ),
    )


class RoleProposal(GuidanceModel):
    """Suggest a dramatic function while leaving appearance vocabulary open."""

    functional_role: FunctionalRole
    persona: str = ""
    sketch: str = Field(min_length=1)


class AdaptedPrompt(GuidanceModel):
    """Tie an adapted question or movement to an item in a selected pattern."""

    skeleton_id: str = Field(pattern=ID_PATTERN)
    source_index: int = Field(ge=0)
    adaptation: str = Field(min_length=1)


class CreativeDeviation(GuidanceModel):
    """Explain a voluntary departure from convention grounded in the premise."""

    proposal: str = Field(min_length=1)
    premise_basis: str = Field(min_length=1)
    convention: str = Field(min_length=1)


class CompositionDraft(GuidanceModel):
    """Offer bounded inspiration or explicitly decline to impose a pattern."""

    abstained: bool = False
    reason: str = Field(min_length=1)
    selections: list[PatternSelectionDraft] = Field(default_factory=list, max_length=4)
    role_suggestions: list[RoleProposal] = Field(default_factory=list)
    questions: list[AdaptedPrompt] = Field(default_factory=list, max_length=2)
    movements: list[AdaptedPrompt] = Field(default_factory=list, max_length=2)
    deviation: CreativeDeviation | None = None


class CompositionArtifact(CompositionDraft):
    """Freeze the exact downstream blocks rather than rerendering a future catalog."""

    # Earlier contract-2 artifacts allow an empty principal connection. Keep them readable.
    selections: list[PatternSelection] = Field(default_factory=list, max_length=4)
    contract_version: Literal[2] = 2
    strategy: Literal["compositional_v2"] = "compositional_v2"
    catalog_version: str
    catalog_hash: str
    catalog_snapshot: list[PlotSkeleton]
    character_block: str = ""
    planning_block: str = ""
    diagnostics: list[str] = Field(default_factory=list)
    attempts: int = 0


class CompositionFailure(GuidanceModel):
    """Distinguish a failed optional composition from a deliberate abstention."""

    contract_version: Literal[2] = 2
    status: Literal["failed"] = "failed"
    diagnostics: list[str]
