"""Shared infrastructure for ASG packages and applications."""

from .audio import (
    NARRATION_VOICE_NAMES,
    NARRATION_VOICES,
    AudioArtifact,
    AudioGenerationError,
    NarrationVoice,
    create_story_audio,
    create_story_audio_sync,
    create_voice_sample,
    create_voice_sample_sync,
    markdown_to_speech_text,
)
from .console import use_utf8_output
from .craft import (
    CraftMetrics,
    craft_metrics,
    prose_paragraphs,
    split_sentences,
)
from .files import artifact_json, atomic_write_csv, atomic_write_json, atomic_write_text
from .locks import file_lock
from .paths import create_unique_directory, find_project_root, slugify, stories_path
from .progress import Progress, format_progress

__all__ = [
    "NARRATION_VOICES",
    "NARRATION_VOICE_NAMES",
    "AudioArtifact",
    "AudioGenerationError",
    "CraftMetrics",
    "NarrationVoice",
    "Progress",
    "artifact_json",
    "atomic_write_csv",
    "atomic_write_json",
    "atomic_write_text",
    "craft_metrics",
    "create_unique_directory",
    "create_story_audio",
    "create_story_audio_sync",
    "create_voice_sample",
    "create_voice_sample_sync",
    "file_lock",
    "find_project_root",
    "format_progress",
    "markdown_to_speech_text",
    "prose_paragraphs",
    "slugify",
    "split_sentences",
    "stories_path",
    "use_utf8_output",
]
