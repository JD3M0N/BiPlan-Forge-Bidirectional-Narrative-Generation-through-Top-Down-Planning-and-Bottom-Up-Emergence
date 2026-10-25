"""What a run leaves on disk about itself: errors, versions, usage and metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)

from ..formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from ..planning.profiles import NarrativeProfile
from ..version import GENERATOR_NAME, GENERATOR_VERSION, PIPELINE_VERSION


class ErrorReport(BaseModel):
    """Represent ErrorReport data and behavior."""

    code: str
    stage: str
    run_id: str
    summary: str
    details: dict = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class GeneratorVersionArtifact(BaseModel):
    """Identify the generator release and artifact contract used by one run."""

    generator: str = GENERATOR_NAME
    generator_version: str = Field(default=GENERATOR_VERSION, pattern=r"^\d+\.\d+\.\d+$")
    pipeline_version: str = Field(default=PIPELINE_VERSION, pattern=r"^\d+\.\d+$")


class LLMUsageRecord(BaseModel):
    """One attempt at one model call, and where in the pipeline it was made.

    Since 7.2 every attempt of a logical call shares its call_id, duration_seconds is that
    attempt's own latency and wait_seconds the waiting that preceded it, so nothing adds up
    earlier attempts; stage is the pipeline stage and agent the one that asked. Before 7.2 each
    attempt had its own call_id, durations accumulated retries and stage repeated operation.
    """

    call_id: str
    decision_id: str = ""
    operation: str
    stage: str
    agent: str = ""
    attempt: int
    status: Literal["succeeded", "failed"]
    model: str
    timestamp: datetime
    duration_seconds: float = 0
    prompt_tokens: int = 0
    candidate_tokens: int = 0
    thoughts_tokens: int = 0
    cached_tokens: int = 0
    total_tokens: int = 0
    retries: int = 0
    wait_seconds: float = 0
    error_code: str | None = None


class LLMUsageArtifact(BaseModel):
    """A run's model usage: logical calls, the attempts they took, and auxiliary requests.

    calls and failed_calls count logical calls (one call_id each; failed when its last attempt
    failed), attempts and failed_attempts count requests, and auxiliary_calls the count_tokens
    preflights, which are never calls. Before 7.2 calls mixed all three.
    """

    records: list[LLMUsageRecord] = Field(default_factory=list)
    calls: int = 0
    failed_calls: int = 0
    attempts: int = 0
    failed_attempts: int = 0
    auxiliary_calls: int = 0
    total_tokens: int = 0
    total_wait_seconds: float = 0


class RunMetadata(BaseModel):
    """Represent RunMetadata data and behavior."""

    run_id: str
    model: str
    created_at: datetime
    updated_at: datetime
    status: Literal["running", "completed", "failed"]
    completed_stages: list[str] = Field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    error_stage: str | None = None
    warnings: list[str] = Field(default_factory=list)
    pipeline_version: str = PIPELINE_VERSION
    story_format: StoryFormat = StoryFormat.NARRATIVE
    script_method: ScriptMethod | None = None
    # Both stay None outside a simulated run, so a narrative or script run's metadata is
    # byte-identical to the one the same pipeline wrote before the hybrid stages existed.
    narrative_voice: NarrativeVoice | None = None
    actor_memory: ActorMemory | None = None
    # The profile the run was generated with, so a run that failed before request.json existed
    # still says what it was asked for (7.2).
    narrative_profile: NarrativeProfile | None = None
    # The model the performance ran on, set only for a simulated run whose performance had a model,
    # key or pace of its own (GEMINI_STAGE_*, 7.4). None means the performance ran on `model`, as
    # every run before 7.4 did; llm_calls.jsonl names the model of each call.
    stage_model: str | None = None
    # The model the reader-facing prose was routed to (GEMINI_PROSE_MODEL, 7.12). None means the
    # prose ran on `model`; models_used says whether the prose model really answered, since it
    # falls back to `model` once its small free allowance is spent.
    prose_model: str | None = None
    # Every model that answered at least one call, sorted (7.7). A provider chain can fail over
    # mid-run, so a run whose list, without stage_model, has more than one model mixed models
    # and is never paired with a single-model run.
    models_used: list[str] = Field(default_factory=list)
