"""Shared infrastructure for ASG packages and applications."""

from .audio import (
    AudioArtifact,
    AudioGenerationError,
    create_story_audio,
    create_story_audio_sync,
    markdown_to_speech_text,
)
from .craft import (
    CraftMetrics,
    craft_metrics,
    prose_paragraphs,
    split_sentences,
)
from .files import atomic_write_json, atomic_write_text
from .locks import file_lock
from .paths import find_project_root, slugify, stories_path

__all__ = [
    "AudioArtifact",
    "AudioGenerationError",
    "CraftMetrics",
    "atomic_write_json",
    "atomic_write_text",
    "craft_metrics",
    "create_story_audio",
    "create_story_audio_sync",
    "file_lock",
    "find_project_root",
    "markdown_to_speech_text",
    "prose_paragraphs",
    "slugify",
    "split_sentences",
    "stories_path",
]
