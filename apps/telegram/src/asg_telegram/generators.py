"""Adapters translating concrete pipelines into the application contract.

This is the only module allowed to import ``asg_stagecraft``. Everything the bot
needs from a pipeline -- progress, events, failures, options, the brief -- is
translated here into the types declared in :mod:`asg_telegram.contract`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from asg_core import NARRATION_VOICES
from asg_stagecraft import CastMember, GenerationOptions, StoryBrief, StoryGenerator
from asg_stagecraft.brief import MAX_CAST, PRONOUN_LABELS, ROLE_LABELS
from asg_stagecraft.formats import (
    FORMAT_COST_HINTS,
    MEMORY_CHOICES,
    OUTPUT_CHOICES,
    OUTPUT_HELP,
    OUTPUT_LABEL,
    VOICE_CHOICES,
    StoryFormat,
    output_choice_for,
)
from asg_stagecraft.options import AUTOMATIC_AUDIO_VOICE_LABEL, MAX_OFFERED_TURNS_PER_BEAT
from asg_stagecraft.planning.profiles import (
    AUTOMATIC_PROFILE_DESCRIPTION,
    AUTOMATIC_PROFILE_LABEL,
    PROFILE_LABELS,
)
from asg_stagecraft.runtime.config import load_settings as load_stagecraft_settings
from asg_stagecraft.runtime.errors import ASGError, RunCancelledError
from asg_stagecraft.runtime.progress import PipelineEvent, ProgressUpdate
from asg_stagecraft.runtime.provider import provider_from_settings
from pydantic import ValidationError

from .contract import (
    BriefSpec,
    EventCallback,
    GenerationCancelled,
    GenerationEvent,
    GenerationFailure,
    GenerationProgress,
    GeneratorUnavailable,
    OptionChoice,
    OptionSpec,
    OptionValue,
    ProgressCallback,
    RunCreatedCallback,
    RunSummary,
    ShouldCancel,
    StoryGeneratorAdapter,
    StoryOutline,
)

_FIELDS = GenerationOptions.model_fields
_SIMULATED = frozenset({StoryFormat.SIMULATED.value})
_TAKES_CHARACTER = tuple(choice.voice.value for choice in VOICE_CHOICES if choice.takes_character)


def _build_option_specs() -> tuple[OptionSpec, ...]:
    """Describe every configurable run option, in the order the panel shows them."""
    format_choices = tuple(
        OptionChoice(
            item.key, item.label, item.description, note=FORMAT_COST_HINTS[item.story_format]
        )
        for item in OUTPUT_CHOICES
    )
    automatic_profile = OptionChoice(None, AUTOMATIC_PROFILE_LABEL, AUTOMATIC_PROFILE_DESCRIPTION)
    profile_choices = (automatic_profile,) + tuple(
        OptionChoice(profile.value, label) for profile, label in PROFILE_LABELS.items()
    )
    voice_choices = tuple(
        OptionChoice(item.voice.value, item.label, item.description) for item in VOICE_CHOICES
    )
    memory_choices = tuple(
        OptionChoice(item.memory.value, item.label, item.description) for item in MEMORY_CHOICES
    )
    audio_voice_choices = (OptionChoice("", AUTOMATIC_AUDIO_VOICE_LABEL),) + tuple(
        OptionChoice(voice.name, f"{voice.display_name} · {voice.gender}", group=voice.country)
        for voice in NARRATION_VOICES
    )
    return (
        OptionSpec("format", "choice", OUTPUT_LABEL, OUTPUT_HELP, format_choices),
        OptionSpec(
            "narrative_profile",
            "choice",
            _FIELDS["narrative_profile"].title,
            _FIELDS["narrative_profile"].description,
            profile_choices,
        ),
        OptionSpec(
            "promise_ledger",
            "toggle",
            _FIELDS["promise_ledger"].title,
            _FIELDS["promise_ledger"].description,
        ),
        OptionSpec(
            "narrative_guidance",
            "toggle",
            _FIELDS["narrative_guidance"].title,
            _FIELDS["narrative_guidance"].description,
        ),
        OptionSpec(
            "narrative_voice",
            "choice",
            _FIELDS["narrative_voice"].title,
            _FIELDS["narrative_voice"].description,
            voice_choices,
            formats=_SIMULATED,
        ),
        OptionSpec(
            "narrator",
            "text",
            _FIELDS["narrator"].title,
            _FIELDS["narrator"].description,
            max_length=80,
            formats=_SIMULATED,
            requires=(("narrative_voice", _TAKES_CHARACTER),),
        ),
        OptionSpec(
            "narration_tone",
            "text",
            _FIELDS["narration_tone"].title,
            _FIELDS["narration_tone"].description,
            max_length=300,
            formats=_SIMULATED,
        ),
        OptionSpec(
            "actor_memory",
            "choice",
            _FIELDS["actor_memory"].title,
            _FIELDS["actor_memory"].description,
            memory_choices,
            formats=_SIMULATED,
        ),
        OptionSpec(
            "simulation_mode",
            "choice",
            _FIELDS["simulation_mode"].title,
            _FIELDS["simulation_mode"].description,
            (OptionChoice("fixed", "Hitos fijos"), OptionChoice("adaptive", "Hitos adaptables")),
            formats=_SIMULATED,
        ),
        OptionSpec(
            "inventory",
            "toggle",
            _FIELDS["inventory"].title,
            _FIELDS["inventory"].description,
            formats=_SIMULATED,
        ),
        OptionSpec(
            "turns_per_beat",
            "integer",
            _FIELDS["turns_per_beat"].title,
            _FIELDS["turns_per_beat"].description,
            minimum=2,
            maximum=MAX_OFFERED_TURNS_PER_BEAT,
            formats=_SIMULATED,
        ),
        OptionSpec("audio", "toggle", _FIELDS["audio"].title, _FIELDS["audio"].description),
        OptionSpec(
            "audio_voice",
            "choice",
            _FIELDS["audio_voice"].title,
            _FIELDS["audio_voice"].description,
            audio_voice_choices,
            requires=(("audio", (True,)),),
            previewable=True,
        ),
    )


_OPTION_SPECS = _build_option_specs()

_BRIEF_SPEC = BriefSpec(
    limits={
        "title": 120,
        "genre": 80,
        "setting": 400,
        "plot": 4000,
        "notes": 1500,
        "name": 80,
        "description": 600,
        "secret": 400,
    },
    max_cast=MAX_CAST,
    roles=tuple(OptionChoice(role, label) for role, label in ROLE_LABELS.items()),
    pronouns=tuple(OptionChoice(pronoun, label) for pronoun, label in PRONOUN_LABELS.items()),
)


def _spanish_message(entry: dict) -> str:
    """Translate one Pydantic error entry's common constraint types into Spanish."""
    kind = entry.get("type", "")
    ctx = entry.get("ctx", {})
    if kind == "value_error":
        message = str(entry.get("msg", ""))
        return message[len("Value error, ") :] if message.startswith("Value error, ") else message
    if kind == "greater_than_equal":
        return f"debe ser mayor o igual que {ctx.get('ge')}."
    if kind in {"string_too_long", "too_long"}:
        limit = ctx.get("max_length") or ctx.get("field_type")
        return f"no puede superar los {limit} caracteres." if limit else "es demasiado largo."
    if kind == "string_too_short":
        return f"debe tener al menos {ctx.get('min_length')} caracteres."
    if kind in {"enum", "literal_error"}:
        return f"debe ser uno de: {ctx.get('expected')}."
    return str(entry.get("msg", "no es válido."))


def _spanish_error(error: ValidationError | ValueError) -> str:
    """Translate a Pydantic or plain validation error into one Spanish sentence."""
    if isinstance(error, ValueError) and not isinstance(error, ValidationError):
        return str(error)
    first = error.errors()[0]
    field_path = ".".join(str(part) for part in first.get("loc", ())) or "opción"
    return f"{field_path}: {_spanish_message(first)}"


class StagecraftGenerator:
    """Adapt the Stagecraft pipeline to the Telegram application contract."""

    def __init__(self) -> None:
        """Resolve settings and build the shared provider exactly once.

        Reading configuration here rather than per story makes a broken setup
        fail at start-up instead of inside a user's chat, and lets every job
        share one provider so the Gemini quota limiter spans all of them.
        """
        try:
            self._settings = load_stagecraft_settings()
            self._provider = provider_from_settings(self._settings)
        except ASGError as error:
            raise GeneratorUnavailable(error.summary) from error
        self._defaults = GenerationOptions.from_settings(self._settings)

    @property
    def display_name(self) -> str:
        """Return the generator name shown to Telegram users."""
        return "Stagecraft"

    @property
    def option_specs(self) -> tuple[OptionSpec, ...]:
        """Return every configurable run option, in panel order."""
        return _OPTION_SPECS

    @property
    def brief_spec(self) -> BriefSpec:
        """Return the limits and choices the guided wizard offers."""
        return _BRIEF_SPEC

    def default_options(self) -> dict[str, OptionValue]:
        """Return this deployment's default value for every option."""
        values = self._defaults.model_dump(mode="json", exclude={"story_format", "script_method"})
        format_key = next(
            item.key
            for item in OUTPUT_CHOICES
            if item.story_format == self._defaults.story_format
            and item.script_method == self._defaults.script_method
        )
        return {"format": format_key, **values}

    def normalize_options(self, values: Mapping[str, OptionValue]) -> dict[str, OptionValue]:
        """Merge, resolve and validate a set of chosen option values."""
        merged: dict[str, OptionValue] = {**self.default_options(), **values}
        known = {spec.key for spec in _OPTION_SPECS}
        merged = {key: value for key, value in merged.items() if key in known}
        try:
            choice = output_choice_for(str(merged.pop("format")))
        except ValueError as exc:
            raise ValueError("Formato de salida desconocido.") from exc
        if merged.get("narrative_voice") not in _TAKES_CHARACTER:
            merged["narrator"] = ""
        try:
            options = self._defaults.with_changes(
                story_format=choice.story_format,
                script_method=choice.script_method,
                **merged,
            )
        except (ValidationError, TypeError, ValueError) as exc:
            raise ValueError(_spanish_error(exc)) from exc
        result = options.model_dump(mode="json", exclude={"story_format", "script_method"})
        return {"format": choice.key, **result}

    def validate_outline(self, outline: StoryOutline) -> None:
        """Reject an outline the pipeline could not turn into a story brief."""
        try:
            self._brief_from(outline)
        except ValidationError as exc:
            raise ValueError(_spanish_error(exc)) from exc

    def startup_details(self) -> tuple[tuple[str, str], ...]:
        """Return the (label, value) rows the operator console shows at start-up."""
        settings = self._settings
        quota = f"{settings.rpm_limit} RPM (reserva {settings.rpm_reserve})"
        if settings.tpm_limit:
            quota += f" · {settings.tpm_limit} TPM"
        else:
            quota += " · TPM sin límite"
        rows = [
            ("Generador", "Stagecraft"),
            ("Modelo", settings.model),
            ("Cuota", quota),
        ]
        if settings.splits_stage:
            # The performance's own model has its own daily quota; the key itself is never shown.
            stage = f"{settings.effective_stage_model} · {settings.effective_stage_rpm_limit} RPM"
            if settings.stage_api_key:
                stage += " · clave propia"
            rows.append(("Modelo de la función", stage))
        rows += [
            ("Clave de Gemini", "configurada" if settings.api_key else "sin configurar"),
            ("Historias", str(settings.output_root)),
        ]
        return tuple(rows)

    def _brief_from(self, outline: StoryOutline) -> StoryBrief:
        """Translate an application outline into the pipeline's structured brief."""
        cast = [
            CastMember(
                name=member.name,
                role=member.role,
                pronoun=member.pronoun,
                description=member.description,
                secret=member.secret,
            )
            for member in outline.cast
        ]
        return StoryBrief(
            plot=outline.plot,
            title=outline.title,
            genre=outline.genre,
            setting=outline.setting,
            cast=cast,
            notes=outline.notes,
        )

    def generate(
        self,
        request: str | StoryOutline,
        *,
        options: Mapping[str, OptionValue] | None = None,
        on_progress: ProgressCallback | None = None,
        on_run_created: RunCreatedCallback | None = None,
        on_event: EventCallback | None = None,
        should_cancel: ShouldCancel | None = None,
    ) -> Path:
        """Generate one story and return its run directory."""
        try:
            normalized = self.normalize_options(options or {})
        except ValueError as exc:
            raise GenerationFailure(
                str(exc), code="INVALID_OPTIONS", stage="configuration"
            ) from exc
        choice = output_choice_for(str(normalized.pop("format")))
        try:
            run_options = self._defaults.with_changes(
                story_format=choice.story_format, script_method=choice.script_method, **normalized
            )
        except (ValidationError, TypeError) as exc:
            raise GenerationFailure(
                _spanish_error(exc), code="INVALID_OPTIONS", stage="configuration"
            ) from exc
        if isinstance(request, StoryOutline):
            try:
                story_request: str | StoryBrief = self._brief_from(request)
            except ValidationError as exc:
                raise GenerationFailure(
                    _spanish_error(exc), code="INVALID_BRIEF", stage="configuration"
                ) from exc
        else:
            story_request = request
        generator = StoryGenerator.from_options(
            self._provider, self._settings.output_root, run_options
        )
        try:
            return generator.generate(
                story_request,
                on_progress=_translate_progress(on_progress),
                on_run_created=on_run_created,
                on_event=_translate_event(on_event),
                should_cancel=should_cancel,
            ).run_dir
        except RunCancelledError as error:
            raise _as_cancelled(error) from error
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
    run_options = _read_json(run_dir / "generation_options.json")
    audio = bool(run_options.get("audio", True)) if isinstance(run_options, dict) else True
    audio_voice = run_options.get("audio_voice", "") if isinstance(run_options, dict) else ""
    return RunSummary(
        usage=_usage_line(run_dir),
        warnings=tuple(_run_warnings(run_dir)),
        document_caption=caption,
        audio=audio,
        audio_voice=str(audio_voice or ""),
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
        callback(GenerationEvent(event.message, event.stage, event.kind))

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


def _as_cancelled(error: RunCancelledError) -> GenerationFailure:
    """Translate a pipeline cancellation into the application's own type."""
    return GenerationCancelled(error.stage)


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


def create_generator(
    name: str, registry: GeneratorRegistry = DEFAULT_REGISTRY
) -> StoryGeneratorAdapter:
    """Create generator."""
    return registry.create(name)
