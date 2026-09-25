"""Public facade for Top-Down story generation."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .errors import RunArtifactError
from .formats import ScriptMethod, StoryFormat
from .pipeline import StoryPipeline
from .profiles import NarrativeProfile
from .progress import PipelineEventCallback, ProgressCallback
from .schemas import StoryRequest
from .version import SUPPORTED_PIPELINE_VERSIONS


class StoryRun:
    """Represent a completed compatible Top-Down run."""

    def __init__(self, run_dir: Path) -> None:
        """Validate and open a completed run directory."""
        self.run_dir = Path(run_dir)
        metadata_path = self.run_dir / "metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RunArtifactError(f"No se encontró metadata.json en {self.run_dir}.") from exc
        except json.JSONDecodeError as exc:
            raise RunArtifactError(f"metadata.json en {self.run_dir} no es JSON válido.") from exc
        if (
            metadata.get("status") != "completed"
            or metadata.get("pipeline_version") not in SUPPORTED_PIPELINE_VERSIONS
        ):
            supported = ", ".join(sorted(SUPPORTED_PIPELINE_VERSIONS))
            raise RunArtifactError(
                f"Only completed Top-Down runs with pipeline versions {supported} "
                "can be opened as StoryRun"
            )
        self.story_format = StoryFormat(metadata.get("story_format") or StoryFormat.NARRATIVE)
        method = metadata.get("script_method")
        self.script_method = ScriptMethod(method) if method else None

    @property
    def story_path(self) -> Path:
        """Return the canonical final story path."""
        return self.run_dir / "story.md"

    @property
    def audio_path(self) -> Path:
        """Return the optional MP3 narration path."""
        return self.run_dir / "story.mp3"

    @property
    def script_path(self) -> Path:
        """Return the structured theater-script path, populated only for script runs."""
        return self.run_dir / "script.json"

    def __fspath__(self) -> str:
        """Expose the run directory through the filesystem path protocol."""
        return str(self.run_dir)


class StoryGenerator:
    """Provide the stable public API for Top-Down generation."""

    def __init__(
        self,
        provider,
        output_root: Path,
        *,
        narrative_guidance: bool = True,
        narrative_profile: NarrativeProfile | None = None,
        audio: bool = True,
        promise_ledger: bool = True,
        story_format: StoryFormat = StoryFormat.NARRATIVE,
        script_method: ScriptMethod = ScriptMethod.NATIVE,
    ) -> None:
        """Configure a generator with its provider and output directory."""
        self.provider = provider
        self.output_root = Path(output_root)
        self.narrative_guidance = narrative_guidance
        self.promise_ledger = promise_ledger
        self.narrative_profile = narrative_profile
        self.audio = audio
        self.story_format = story_format
        self.script_method = script_method

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
            on_progress=on_progress,
            on_run_created=on_run_created,
            on_event=on_event,
            narrative_guidance=self.narrative_guidance,
            promise_ledger=self.promise_ledger,
            narrative_profile=self.narrative_profile,
            audio=self.audio,
            story_format=self.story_format,
            script_method=self.script_method,
        )
        return StoryRun(pipeline.execute(request))
