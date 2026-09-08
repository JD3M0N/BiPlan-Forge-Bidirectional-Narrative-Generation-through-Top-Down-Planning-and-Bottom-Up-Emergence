"""Adapters translating concrete pipelines into the application contract.

This is the only module allowed to import ``asg_top_down``. Everything the bot
needs from a pipeline -- progress, events, failures, warnings, profiles -- is
translated here into the types declared in :mod:`asg_telegram.contract`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from asg_top_down import StoryGenerator
from asg_top_down.config import load_settings as load_top_down_settings
from asg_top_down.errors import ASGError
from asg_top_down.profiles import PROFILE_LABELS, NarrativeProfile
from asg_top_down.progress import PipelineEvent, ProgressUpdate
from asg_top_down.provider import provider_from_settings

from .contract import (
    EventCallback,
    GenerationEvent,
    GenerationFailure,
    GenerationProgress,
    ProfileOption,
    ProgressCallback,
    RunCreatedCallback,
    RunSummary,
    StoryGeneratorAdapter,
)


class TopDownGenerator:
    """Adapt the Top-Down pipeline to the Telegram application contract."""

    def __init__(self) -> None:
        """Resolve settings and build the shared provider exactly once.

        Reading configuration here rather than per story makes a broken setup
        fail at start-up instead of inside a user's chat, and lets every job
        share one provider so the Gemini quota limiter spans all of them.
        """
        self._settings = load_top_down_settings()
        self._provider = provider_from_settings(self._settings)

    @property
    def display_name(self) -> str:
        """Return the generator name shown to Telegram users."""
        return "Top-Down"

    @property
    def profiles(self) -> tuple[ProfileOption, ...]:
        """Return the narrative profiles a user may choose between."""
        return tuple(
            ProfileOption(profile.value, label, (profile.value, label.casefold()))
            for profile, label in PROFILE_LABELS.items()
        )

    def generate(
        self,
        prompt: str,
        *,
        narrative_profile: str | None = None,
        on_progress: ProgressCallback | None = None,
        on_run_created: RunCreatedCallback | None = None,
        on_event: EventCallback | None = None,
    ) -> Path:
        """Generate one story and return its run directory."""
        generator = StoryGenerator(
            self._provider,
            self._settings.output_root,
            narrative_guidance=self._settings.narrative_guidance,
            narrative_profile=NarrativeProfile(narrative_profile) if narrative_profile else None,
        )
        try:
            return generator.generate(
                prompt,
                on_progress=_translate_progress(on_progress),
                on_run_created=on_run_created,
                on_event=_translate_event(on_event),
            ).run_dir
        except ASGError as error:
            raise _as_failure(error) from error

    def summarize(self, run_dir: Path) -> RunSummary:
        """Read a finished run and describe it for the chat."""
        return summarize_run(run_dir)


def summarize_run(run_dir: Path) -> RunSummary:
    """Describe one finished Top-Down run from the artifacts it left behind."""
    return RunSummary(usage=_usage_line(run_dir), warnings=tuple(_run_warnings(run_dir)))


def _translate_progress(callback: ProgressCallback | None) -> Callable | None:
    """Wrap an application progress callback for the pipeline to call."""
    if callback is None:
        return None

    def forward(update: ProgressUpdate) -> None:
        """Forward one pipeline milestone through the application contract."""
        callback(GenerationProgress(update.percent, update.stage, update.description))

    return forward


def _translate_event(callback: EventCallback | None) -> Callable | None:
    """Wrap an application event callback for the pipeline to call."""
    if callback is None:
        return None

    def forward(event: PipelineEvent) -> None:
        """Forward one pipeline event through the application contract."""
        callback(GenerationEvent(event.message, event.stage))

    return forward


def _as_failure(error: ASGError) -> GenerationFailure:
    """Translate a structured pipeline error into an application failure."""
    return GenerationFailure(
        error.summary,
        code=error.code,
        stage=error.stage,
        recommendation=error.recommendations[0] if error.recommendations else None,
        run_id=error.run_id,
    )


def _read_json(path: Path) -> Any:
    """Read one optional JSON artifact, treating unreadable files as absent."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _usage_line(run_dir: Path) -> str | None:
    """Summarize Gemini consumption for a finished run, when it was recorded."""
    usage = _read_json(run_dir / "llm_usage_summary.json")
    if not isinstance(usage, dict):
        return None
    return (
        f"Gemini: {usage.get('calls', 0)} llamadas, "
        f"{usage.get('total_tokens', 0)} tokens, "
        f"{round(usage.get('total_wait_seconds', 0))}s esperando cuota."
    )


def _run_warnings(run_dir: Path) -> list[str]:
    """Expand a run's recorded warnings into actionable Spanish messages."""
    metadata = _read_json(run_dir / "metadata.json")
    if not isinstance(metadata, dict):
        return []
    warnings = [str(warning) for warning in metadata.get("warnings", [])]
    if not warnings:
        return []
    details = _revision_warning_details(run_dir)
    if not details:
        return warnings
    return details + [
        warning for warning in warnings if not warning.startswith("[WRITER_REVISION_REJECTED]")
    ]


def _revision_warning_details(run_dir: Path) -> list[str]:
    """Format structured Writer fallbacks and the resulting length impact."""
    report = _read_json(run_dir / "revision_report.json")
    if not isinstance(report, dict):
        return []
    details = [
        _chapter_warning(chapter)
        for chapter in report.get("chapters", [])
        if chapter.get("warning_code") == "WRITER_REVISION_REJECTED"
    ]
    if not details:
        return details
    audit = _read_json(run_dir / "length_audit.json")
    total = audit.get("total", {}) if isinstance(audit, dict) else {}
    if total and not total.get("within_tolerance", True):
        details.append(
            f"Longitud final: {total.get('actual_words')} palabras; mínimo esperado "
            f"{total.get('minimum_words')} y objetivo {total.get('target_words')}."
        )
    return details


def _chapter_warning(chapter: dict) -> str:
    """Describe why one chapter fell back to its unrevised draft."""
    attempts = chapter.get("attempts", [])
    diagnostics = [
        attempt.get("diagnostic")
        for attempt in attempts
        if attempt.get("status") == "rejected" and attempt.get("diagnostic")
    ]
    if diagnostics and all(
        diagnostic.get("code") == "WORD_COUNT_OUT_OF_RANGE" for diagnostic in diagnostics
    ):
        counts = " y ".join(str(diagnostic.get("actual_words", "?")) for diagnostic in diagnostics)
        latest = diagnostics[-1]
        return (
            f"Capítulo {chapter.get('chapter_index')}: {len(diagnostics)} "
            f"revisiones descartadas por longitud ({counts} palabras; rango válido "
            f"{latest.get('minimum_words')}-{latest.get('maximum_words')}). "
            f"Se entregó el borrador de {chapter.get('draft_words')} palabras. "
            "Código: WRITER_REVISION_REJECTED."
        )
    failed = [
        attempt.get("exception_type", "error interno")
        for attempt in attempts
        if attempt.get("status") == "failed"
    ]
    reasons = [diagnostic.get("code", "RECHAZO_DESCONOCIDO") for diagnostic in diagnostics] + failed
    joined = ", ".join(reasons) or "sin diagnóstico"
    return (
        f"Capítulo {chapter.get('chapter_index')}: no hubo una revisión válida "
        f"({joined}). Se entregó el borrador de "
        f"{chapter.get('draft_words')} palabras. Código: WRITER_REVISION_REJECTED."
    )


GeneratorFactory = Callable[[], StoryGeneratorAdapter]


class GeneratorRegistry:
    """Resolve a generator name into a configured adapter instance."""

    def __init__(self) -> None:
        """Initialize the GeneratorRegistry instance."""
        self._factories: dict[str, GeneratorFactory] = {}

    def register(self, name: str, factory: GeneratorFactory) -> None:
        """Register one adapter factory under a normalized name."""
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("El nombre del generador no puede estar vacío.")
        self._factories[normalized] = factory

    @property
    def available(self) -> tuple[str, ...]:
        """Return every registered generator name in alphabetical order."""
        return tuple(sorted(self._factories))

    def create(self, name: str) -> StoryGeneratorAdapter:
        """Build the adapter registered under a name."""
        normalized = name.strip().lower()
        try:
            factory = self._factories[normalized]
        except KeyError as exc:
            choices = ", ".join(self.available) or "ninguno"
            raise ValueError(f"Generador desconocido '{name}'. Disponibles: {choices}.") from exc
        return factory()


DEFAULT_REGISTRY = GeneratorRegistry()
DEFAULT_REGISTRY.register("top-down", TopDownGenerator)


def create_generator(
    name: str, registry: GeneratorRegistry = DEFAULT_REGISTRY
) -> StoryGeneratorAdapter:
    """Create generator."""
    return registry.create(name)
