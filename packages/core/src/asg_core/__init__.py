"""Shared infrastructure for ASG packages and applications."""

from .audio import (
    AudioArtifact,
    AudioGenerationError,
    create_story_audio,
    create_story_audio_sync,
    markdown_to_speech_text,
)
from .files import atomic_write_json, atomic_write_text
from .paths import find_project_root, slugify, stories_path

__all__ = [
    "AudioArtifact",
    "AudioGenerationError",
    "atomic_write_json",
    "atomic_write_text",
    "create_story_audio",
    "create_story_audio_sync",
    "find_project_root",
    "markdown_to_speech_text",
    "slugify",
    "stories_path",
]
