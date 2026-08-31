"""Public facade for Top-Down story generation."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .pipeline import StoryPipeline
from .progress import PipelineEventCallback, ProgressCallback
from .schemas import StoryRequest
from .version import SUPPORTED_PIPELINE_VERSIONS


class StoryRun:
    """Represent a completed compatible Top-Down 5.x run."""

    def __init__(self, run_dir: Path) -> None:
        """Validate and open a completed run directory."""
        self.run_dir = Path(run_dir)
        metadata_path = self.run_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            metadata.get("status") != "completed"
            or metadata.get("pipeline_version") not in SUPPORTED_PIPELINE_VERSIONS
        ):
            supported = ", ".join(sorted(SUPPORTED_PIPELINE_VERSIONS))
            raise ValueError(
                f"Only completed Top-Down runs with pipeline versions {supported} "
                "can be opened as StoryRun"
            )

    @property
    def story_path(self) -> Path:
        """Return the canonical final story path."""
        return self.run_dir / "story.md"

    @property
    def audio_path(self) -> Path:
        """Return the optional MP3 narration path."""
        return self.run_dir / "story.mp3"

    def __fspath__(self) -> str:
        """Expose the run directory through the filesystem path protocol."""
        return str(self.run_dir)


class StoryGenerator:
    """Provide the stable public API for Top-Down generation."""

    def __init__(
        self,
        provider,
        output_root: Path,
        default_target_words: int = 1500,
    ) -> None:
        """Configure a generator with its provider and output directory."""
        if not 300 <= default_target_words <= 20_000:
            raise ValueError("default_target_words must be between 300 and 20000")
        self.provider = provider
        self.output_root = Path(output_root)
        self.default_target_words = default_target_words

    def generate(
        self,
        request: StoryRequest | str,
        on_progress: ProgressCallback | None = None,
        on_run_created: Callable[[Path], None] | None = None,
        on_event: PipelineEventCallback | None = None,
    ) -> StoryRun:
        """Generate one complete story and return its run handle."""
        pipeline = StoryPipeline(
            self.provider,
            self.output_root,
            self.default_target_words,
            on_progress=on_progress,
            on_run_created=on_run_created,
            on_event=on_event,
        )
        return StoryRun(pipeline.execute(request))

    def run(
        self,
        request: StoryRequest | str,
        on_progress: ProgressCallback | None = None,
        on_run_created: Callable[[Path], None] | None = None,
        on_event: PipelineEventCallback | None = None,
    ) -> StoryRun:
        """Alias generate for command and application integrations."""
        return self.generate(
            request,
            on_progress=on_progress,
            on_run_created=on_run_created,
            on_event=on_event,
        )
