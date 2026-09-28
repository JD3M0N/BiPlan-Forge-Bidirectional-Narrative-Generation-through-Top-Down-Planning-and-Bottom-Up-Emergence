"""Adapters translating concrete pipelines into the application contract.

This is the only module allowed to import ``asg_stagecraft``. Everything the bot
needs from a pipeline -- progress, events, failures, warnings, profiles -- is
translated here into the types declared in :mod:`asg_telegram.contract`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from asg_stagecraft import GenerationOptions, StoryGenerator
from asg_stagecraft.formats import OUTPUT_CHOICES, output_choice_for
from asg_stagecraft.planning.profiles import PROFILE_LABELS, NarrativeProfile
from asg_stagecraft.runtime.config import load_settings as load_stagecraft_settings
from asg_stagecraft.runtime.errors import ASGError
from asg_stagecraft.runtime.progress import PipelineEvent, ProgressUpdate
from asg_stagecraft.runtime.provider import provider_from_settings

from .contract import (
    EventCallback,
    FormatOption,
    GenerationEvent,
    GenerationFailure,
    GenerationProgress,
    ProfileOption,
    ProgressCallback,
    RunCreatedCallback,
    RunSummary,
    StoryGeneratorAdapter,
)


class StagecraftGenerator:
    """Adapt the Stagecraft pipeline to the Telegram application contract."""

    def __init__(self) -> None:
        """Resolve settings and build the shared provider exactly once.

        Reading configuration here rather than per story makes a broken setup
        fail at start-up instead of inside a user's chat, and lets every job
        share one provider so the Gemini quota limiter spans all of them.
        """
        self._settings = load_stagecraft_settings()
        self._provider = provider_from_settings(self._settings)

    @property
    def display_name(self) -> str:
        """Return the generator name shown to Telegram users."""
        return "Stagecraft"

    @property
    def profiles(self) -> tuple[ProfileOption, ...]:
        """Return the narrative profiles a user may choose between."""
        return tuple(
            ProfileOption(profile.value, label, (profile.value, label.casefold()))
            for profile, label in PROFILE_LABELS.items()
        )

    @property
    def formats(self) -> tuple[FormatOption, ...]:
        """Return the output choices a user may choose between."""
        return tuple(FormatOption(choice.key, choice.label) for choice in OUTPUT_CHOICES)

    def generate(
        self,
        prompt: str,
        *,
        narrative_profile: str | None = None,
        story_format: str | None = None,
        on_progress: ProgressCallback | None = None,
        on_run_created: RunCreatedCallback | None = None,
        on_event: EventCallback | None = None,
    ) -> Path:
        """Generate one story and return its run directory."""
        if story_format:
            try:
                choice = output_choice_for(story_format)
            except ValueError as exc:
                raise GenerationFailure(
                    "Formato de salida desconocido.",
                    code="UNKNOWN_STORY_FORMAT",
                    stage="configuration",
                ) from exc
        else:
            choice = None
        # The bot exposes no point-of-view step yet, so a simulated run narrates with whatever
        # the deployment configured, like its memory and turn budget. Tracked in TODO.md.
        options = GenerationOptions.from_settings(
            self._settings,
            narrative_profile=NarrativeProfile(narrative_profile) if narrative_profile else None,
            story_format=choice.story_format if choice else None,
            script_method=choice.script_method if choice else None,
        )
        generator = StoryGenerator.from_options(self._provider, self._settings.output_root, options)
        try:
            return generator.generate(
                prompt,
                on_progress=_translate_progress(on_progress),
                on_run_created=on_run_created,
                on_event=_translate_event(on_event),
            ).run_dir
        except ASGError as error:
            raise _as_failure(error) from error
        finally:
            # Jobs run one after another on this one provider, and each run has already written
            # its own usage to disk: keeping the records only grew the bot's memory without end.
            self._provider.usage_records.clear()

    def summarize(self, run_dir: Path) -> RunSummary:
        """Read a finished run and describe it for the chat."""
        return summarize_run(run_dir)


def summarize_run(run_dir: Path) -> RunSummary:
    """Describe one finished Stagecraft run from the artifacts it left behind."""
    metadata = _read_json(run_dir / "metadata.json")
    story_format = metadata.get("story_format") if isinstance(metadata, dict) else None
    caption = {
        "script": "Guion teatral completo en formato Markdown.",
        "simulated": "Historia simulada por los personajes, en formato Markdown.",
    }.get(story_format, "Historia completa en formato Markdown.")
    return RunSummary(
        usage=_usage_line(run_dir),
        warnings=tuple(_run_warnings(run_dir)),
        document_caption=caption,
    )


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
    usage = _read_json(run_dir / "llm_usage.json")
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
    """Format the structured Writer fallbacks recorded in the revision report."""
    report = _read_json(run_dir / "revision_report.json")
    if not isinstance(report, dict):
        return []
    return [
        _chapter_warning(chapter)
        for chapter in report.get("chapters", [])
        if chapter.get("warning_code") == "WRITER_REVISION_REJECTED"
    ]


def _chapter_warning(chapter: dict) -> str:
    """Describe why one chapter fell back to its unrevised draft."""
    attempts = chapter.get("attempts", [])
    diagnostics = [
        attempt.get("diagnostic")
        for attempt in attempts
        if attempt.get("status") == "rejected" and attempt.get("diagnostic")
    ]
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
DEFAULT_REGISTRY.register("stagecraft", StagecraftGenerator)
# "top-down" stays registered as an alias: STORY_GENERATOR is set in deployed
# environments that predate the rename, and a missing name aborts start-up.
DEFAULT_REGISTRY.register("top-down", StagecraftGenerator)


def create_generator(
    name: str, registry: GeneratorRegistry = DEFAULT_REGISTRY
) -> StoryGeneratorAdapter:
    """Create generator."""
    return registry.create(name)
