"""Shared text-to-speech support for generated story artifacts."""

from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp
import edge_tts
from edge_tts import VoicesManager
from langdetect import DetectorFactory, LangDetectException, detect

from .files import atomic_write_json

DetectorFactory.seed = 0

DEFAULT_RETRY_DELAYS = (1.0, 2.0)
DEFAULT_FALLBACK_VOICE = "en-US-EmmaMultilingualNeural"
_VOICE_MANAGER: VoicesManager | None = None


@dataclass(frozen=True)
class AudioArtifact:
    """Describe a successfully synthesized story audio artifact."""

    path: Path
    language: str
    voice: str


class AudioGenerationError(RuntimeError):
    """Report a controlled failure while creating story audio."""


def markdown_to_speech_text(markdown: str) -> str:
    """Convert generated Markdown into clean text suitable for narration."""
    text = re.sub(r"```.*?```", " ", markdown, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[([^]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _fallback_voice() -> str:
    """Return the configured fallback voice, or the built-in default."""
    configured = os.getenv("TTS_FALLBACK_VOICE", "").strip()
    if configured:
        return configured
    return DEFAULT_FALLBACK_VOICE


def _detect_language(text: str) -> str:
    """Detect the language of a text, or "und" if detection fails."""
    try:
        return detect(text)
    except LangDetectException:
        return "und"


async def _voice_for_language(
    language: str, fallback: str, voice_manager: VoicesManager | None = None
) -> str:
    """Select a narration voice for a language, favoring Novel-tagged voices.

    Spanish always resolves to a fixed Spain voice by design. Other languages
    query ``VoicesManager`` and fall back to ``fallback`` on failure.
    """
    global _VOICE_MANAGER

    # Español de España, nunca español de Argentina
    if language.lower().split("-", 1)[0] == "es":
        return "es-ES-AlvaroNeural"
        # Alternativa femenina: "es-ES-ElviraNeural"

    if language == "und":
        return fallback

    try:
        if voice_manager is not None:
            manager = voice_manager
        else:
            if _VOICE_MANAGER is None:
                _VOICE_MANAGER = await VoicesManager.create()
            manager = _VOICE_MANAGER

        candidates = manager.find(Language=language.split("-", 1)[0].lower())
    except (aiohttp.ClientError, TimeoutError, OSError):
        return fallback

    if not candidates:
        return fallback

    def priority(voice: dict[str, Any]) -> tuple[int, str]:
        """Rank a candidate voice, preferring Novel-tagged over General."""
        categories = voice.get("VoiceTag", {}).get("ContentCategories", [])
        rank = 0 if "Novel" in categories else 1 if "General" in categories else 2
        return rank, str(voice.get("ShortName", voice.get("Name", "")))

    selected = min(candidates, key=priority)
    return str(selected.get("ShortName") or selected["Name"])


def _metadata_path(story_path: Path) -> Path:
    """Return the audio metadata path sibling to a story file."""
    return story_path.with_name("audio.json")


def _read_completed_artifact(story_path: Path, output_path: Path) -> AudioArtifact | None:
    """Return the previously completed audio artifact, if one is valid."""
    metadata_path = _metadata_path(story_path)
    if not output_path.is_file() or output_path.stat().st_size == 0 or not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("status") != "completed":
            return None
        return AudioArtifact(
            path=output_path,
            language=str(metadata["language"]),
            voice=str(metadata["voice"]),
        )
    except (OSError, KeyError, TypeError, ValueError):
        return None


def _write_metadata(
    story_path: Path,
    *,
    status: str,
    output_path: Path,
    language: str,
    voice: str,
    error: str | None = None,
) -> None:
    """Write the audio generation status and details to disk."""
    atomic_write_json(
        _metadata_path(story_path),
        {
            "status": status,
            "source": story_path.name,
            "output": output_path.name,
            "format": "mp3",
            "language": language,
            "voice": voice,
            "generated_at": datetime.now(UTC).isoformat(),
            "error": error,
        },
    )


async def _synthesize_with_retries(
    text: str,
    voice: str,
    destination: Path,
    retry_delays: tuple[float, ...],
) -> None:
    """Write a non-empty MP3, retrying failures without leaving partial files."""
    last_error: Exception | None = None
    for attempt in range(len(retry_delays) + 1):
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        try:
            await edge_tts.Communicate(text, voice).save(str(temporary))
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise OSError("edge-tts produced an empty audio file")
            await asyncio.to_thread(os.replace, temporary, destination)
            return
        except Exception as exc:
            last_error = exc
            temporary.unlink(missing_ok=True)
            if attempt < len(retry_delays):
                await asyncio.sleep(retry_delays[attempt])
    assert last_error is not None
    raise last_error


async def create_story_audio(
    story_path: str | Path,
    output_path: str | Path | None = None,
    *,
    retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS,
    force: bool = False,
    voice_manager: VoicesManager | None = None,
) -> AudioArtifact:
    """Create or reuse an MP3 narration for one generated Markdown story."""
    source = Path(story_path)
    destination = Path(output_path) if output_path is not None else source.with_suffix(".mp3")
    if not force:
        existing = _read_completed_artifact(source, destination)
        if existing is not None:
            return existing

    fallback = _fallback_voice()
    language = "und"
    voice = fallback
    try:
        if not source.is_file():
            raise FileNotFoundError(f"Story file does not exist: {source}")
        markdown = await asyncio.to_thread(source.read_text, encoding="utf-8")
        text = markdown_to_speech_text(markdown)
        if not text:
            raise ValueError("Story text is empty after Markdown normalization")
        language = await asyncio.to_thread(_detect_language, text)
        voice = await _voice_for_language(language, fallback, voice_manager)
        destination.parent.mkdir(parents=True, exist_ok=True)
        await _synthesize_with_retries(text, voice, destination, retry_delays)
        artifact = AudioArtifact(destination, language, voice)
        _write_metadata(
            source,
            status="completed",
            output_path=destination,
            language=language,
            voice=voice,
        )
        return artifact
    except Exception as exc:
        try:
            _write_metadata(
                source,
                status="failed",
                output_path=destination,
                language=language,
                voice=voice,
                error=type(exc).__name__,
            )
        except OSError:
            pass
        raise AudioGenerationError(f"Could not create audio for {source.name}") from exc


def create_story_audio_sync(
    story_path: str | Path,
    output_path: str | Path | None = None,
    *,
    retry_delays: tuple[float, ...] = DEFAULT_RETRY_DELAYS,
    force: bool = False,
) -> AudioArtifact:
    """Synchronously create story audio, including from an active event loop."""

    def run() -> AudioArtifact:
        """Run story audio creation to completion in a fresh event loop."""
        return asyncio.run(
            create_story_audio(
                story_path,
                output_path,
                retry_delays=retry_delays,
                force=force,
            )
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return run()
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(run).result()
