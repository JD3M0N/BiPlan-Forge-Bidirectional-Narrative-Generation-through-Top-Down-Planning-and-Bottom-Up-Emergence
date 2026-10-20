"""Progress, events and usage accounting of a run, mixed into StoryPipeline (7.20, ING-3).

Split from pipeline.py with the rest of ING-3. Like every stage mixin, it assumes the
attributes pipeline.py defines: self.repository, self.provider, self.progress and the
callbacks.
"""

from __future__ import annotations

from ..schemas import LLMUsageArtifact
from .progress import (
    PipelineEvent,
    ProgressUpdate,
)
from .provider import COUNT_TOKENS_OPERATION

# Canonical order of pipeline checkpoint stages, shared by every _notify/complete_stage
# pair below; "rate_limit" is intentionally excluded (see _notify).
CHECKPOINT_STAGES = (
    "analysis",
    "architecture",
    "world",
    "characters",
    "planning",
    "plan_review",
    "promises",
    # The scene cards of a narrative run, only when the scene_cards option is on (7.17).
    "scene_cards",
    "drafting",
    "critique",
    "revision",
    "adaptation",
    # The hybrid stages of a simulated run: the cast bible, the props when the inventory is on,
    # the performance the actors improvise from the frozen script, and the prose narrated from
    # its log.
    "casting",
    "props",
    "performance",
    "narration",
    "story",
    "audio",
)

# In a simulated run the script is the director's book rather than the deliverable, so every
# stage up to and including the drafted script is compressed into the first half of the
# progress range and the performance and narration own the rest.
PRE_PERFORMANCE_CEILING = 48
PRE_PERFORMANCE_STAGES = frozenset(CHECKPOINT_STAGES[: CHECKPOINT_STAGES.index("casting")])


class RunReportingMixin:
    """Report a run's progress, its events and what each model call cost."""

    def _report_artifact(self, filename: str, created: bool) -> None:
        """Emit a structured event when an artifact is written."""
        self._emit(
            "artifact_created" if created else "artifact_updated",
            f"artefacto {filename} {'creado' if created else 'actualizado'}",
            stage=self.progress["stage"],
            artifact=filename,
        )

    def _report_wait(self, seconds: int, reason: str) -> None:
        """Report provider retry waits through the pipeline progress channel."""
        self._notify(
            self.progress["percent"],
            "rate_limit",
            f"Esperando {seconds}s: {reason}",
        )

    def _configure_provider_callbacks(self) -> None:
        """Route provider quota and usage events into pipeline callbacks."""
        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = self._report_wait
        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = self._record_usage

    def _clear_provider_callbacks(self) -> None:
        """Detach per-run provider callbacks after completion or failure."""
        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = None
        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = None

    def _record_usage(self, record) -> None:
        """Persist one provider usage record and refresh the aggregate."""
        assert self.repository is not None
        self.repository.append_llm_call(record)
        self._save_usage()

    def _usage_artifact(self) -> LLMUsageArtifact:
        """Aggregate this run's provider usage into logical calls, attempts and auxiliaries.

        A call is every attempt sharing one call_id, and it failed when its last attempt did.
        Before 7.2 each failed attempt counted as a failed call and token counts as calls.
        """
        records = list(getattr(self.provider, "usage_records", []))[self.usage_start :]
        requests = [item for item in records if item.operation != COUNT_TOKENS_OPERATION]
        last_attempt = {item.call_id: item for item in requests}
        return LLMUsageArtifact(
            records=records,
            calls=len(last_attempt),
            failed_calls=sum(item.status == "failed" for item in last_attempt.values()),
            attempts=len(requests),
            failed_attempts=sum(item.status == "failed" for item in requests),
            auxiliary_calls=len(records) - len(requests),
            total_tokens=sum(item.total_tokens for item in records),
            total_wait_seconds=sum(item.wait_seconds for item in records),
        )

    def _save_usage(self) -> None:
        """Write the current aggregate LLM usage artifact."""
        assert self.repository is not None
        self.repository.save_json("llm_usage.json", self._usage_artifact())

    def _notify(
        self,
        percent: int,
        stage: str,
        description: str,
        chapter: int | None = None,
        total: int | None = None,
    ) -> None:
        """Update internal progress and invoke the external progress callback."""
        percent = self._scaled(percent, stage)
        # "rate_limit" is a transient wait notification, not a pipeline checkpoint, so it
        # must not overwrite the real in-progress stage reported by _record_failure.
        if stage != "rate_limit":
            self.progress.update(percent=percent, stage=stage)
        if self.on_progress:
            self.on_progress(ProgressUpdate(percent, stage, description, chapter, total))

    def _scaled(self, percent: int, stage: str) -> int:
        """Compress the pre-performance stages into the first half of a simulated run.

        Writing the script is the whole job of a script run and only the first half of a
        simulated one, so its stages would otherwise report 96% with the performance and the
        narration still to come, and progress would jump backwards at the casting stage.
        """
        if not self._simulated or stage not in PRE_PERFORMANCE_STAGES:
            return percent
        return percent * PRE_PERFORMANCE_CEILING // 100

    def _emit(
        self,
        kind: str,
        message: str,
        *,
        stage: str | None = None,
        attempt: int | None = None,
        artifact: str | None = None,
    ) -> None:
        """Publish a structured pipeline event when a callback is configured."""
        if self.on_event:
            self.on_event(
                PipelineEvent(
                    kind=kind,
                    message=message,
                    stage=stage,
                    attempt=attempt,
                    artifact=artifact,
                )
            )
