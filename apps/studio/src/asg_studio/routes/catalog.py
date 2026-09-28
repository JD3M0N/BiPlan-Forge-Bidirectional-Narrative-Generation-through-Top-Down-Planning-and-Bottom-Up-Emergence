"""Routes that describe what can be asked: health, the option catalog, previews, voice samples."""

from __future__ import annotations

from asg_core import NARRATION_VOICE_NAMES, AudioGenerationError, create_voice_sample_sync
from asg_stagecraft import GenerationOptions, __version__
from asg_stagecraft.formats import StoryFormat
from asg_stagecraft.runtime.errors import ASGError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..catalog import catalog_document
from ..jobs import JobRequest

router = APIRouter(prefix="/api")

# The interface opens on the format it exists for; every other default comes from .env.
INTERFACE_FORMAT = StoryFormat.SIMULATED


def _settings(request: Request):
    """Read the settings without requiring the key, or None when they cannot be read."""
    try:
        return request.app.state.settings_loader(require_api_key=False)
    except (ASGError, OSError, RuntimeError):
        return None


@router.get("/health")
def health(request: Request) -> dict:
    """Say whether generation can start, with which model, and whether this is a demo."""
    settings = _settings(request)
    return {
        "name": "StageCraft",
        "generator_version": __version__,
        "key_present": bool(settings and settings.api_key),
        "model": getattr(settings, "model", None),
        "demo": request.app.state.demo,
    }


@router.get("/catalog")
def catalog(request: Request) -> dict:
    """Return every option the interface draws, with the defaults to preselect."""
    settings = _settings(request)
    defaults = GenerationOptions.from_settings(settings) if settings else GenerationOptions()
    return catalog_document(defaults.with_changes(story_format=INTERFACE_FORMAT))


def _quoted(value: str) -> str:
    """Quote one value for a PowerShell command line."""
    return "'" + value.replace("'", "''") + "'"


def command_line(job: JobRequest) -> str:
    """Write the generate-story command that would run the same request from a terminal."""
    options, defaults = job.options, GenerationOptions()
    parts = ["generate-story"]
    parts += ["--brief", "brief.json"] if job.mode == "brief" else [_quoted(job.prompt.strip())]
    flags = [
        ("--format", options.story_format.value, options.story_format != defaults.story_format),
        (
            "--script-method",
            options.script_method.value,
            options.story_format is StoryFormat.SCRIPT,
        ),
        ("--profile", options.narrative_profile.value if options.narrative_profile else "", True),
        ("--voice", options.narrative_voice.value, options.story_format is INTERFACE_FORMAT),
        ("--narrator", options.narrator, True),
        ("--tone", options.narration_tone, True),
        (
            "--actor-memory",
            options.actor_memory.value,
            options.story_format is INTERFACE_FORMAT,
        ),
        (
            "--turns-per-beat",
            str(options.turns_per_beat),
            options.turns_per_beat != defaults.turns_per_beat,
        ),
        ("--audio-voice", options.audio_voice, True),
    ]
    for flag, value, wanted in flags:
        if wanted and value:
            parts += [flag, _quoted(value) if " " in value else value]
    if not options.audio:
        parts.append("--no-audio")
    prefix = [
        f"$env:{name}='false';"
        for name, enabled in (
            ("ASG_PROMISE_LEDGER", options.promise_ledger),
            ("ASG_NARRATIVE_GUIDANCE", options.narrative_guidance),
        )
        if not enabled
    ]
    return " ".join([*prefix, *parts])


@router.post("/preview")
def preview(job: JobRequest) -> dict:
    """Show the exact prompt a request becomes and the command that repeats it, at no cost."""
    request = job.story_request()
    return {
        "prompt": request if isinstance(request, str) else request.to_prompt(),
        "command": command_line(job),
        "brief": job.brief.model_dump(mode="json") if job.brief else None,
    }


@router.get("/voices/{voice}/sample")
def voice_sample(voice: str, request: Request) -> FileResponse:
    """Read one line with a narration voice, so it can be heard before it is chosen."""
    if voice not in NARRATION_VOICE_NAMES:
        raise HTTPException(status_code=404, detail="Esa voz no existe.")
    path = request.app.state.cache_dir / "voices" / f"{voice}.mp3"
    if not path.is_file() or path.stat().st_size == 0:
        try:
            create_voice_sample_sync(voice, path)
        except AudioGenerationError as exc:
            raise HTTPException(
                status_code=503, detail="No se pudo generar la muestra: hace falta conexión."
            ) from exc
    return FileResponse(path, media_type="audio/mpeg")
