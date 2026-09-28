"""Public facade for Stagecraft story generation."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .brief import StoryBrief
from .formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from .options import GenerationOptions
from .pipeline import StoryPipeline
from .planning.profiles import NarrativeProfile
from .runtime.errors import RunArtifactError
from .runtime.progress import PipelineEventCallback, ProgressCallback
from .schemas import StoryRequest
from .version import SUPPORTED_PIPELINE_VERSIONS


class StoryRun:
    """Represent a completed compatible Stagecraft run."""

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
                f"Only completed Stagecraft runs with pipeline versions {supported} "
                "can be opened as StoryRun"
            )
        self.story_format = StoryFormat(metadata.get("story_format") or StoryFormat.NARRATIVE)
        method = metadata.get("script_method")
        self.script_method = ScriptMethod(method) if method else None
        voice = metadata.get("narrative_voice")
        self.narrative_voice = NarrativeVoice(voice) if voice else None
        memory = metadata.get("actor_memory")
        self.actor_memory = ActorMemory(memory) if memory else None

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
        """Return the structured theater-script path, written by script and simulated runs."""
        return self.run_dir / "script.json"

    @property
    def performance_path(self) -> Path:
        """Return the performance log path, populated only for simulated runs."""
        return self.run_dir / "performance.json"

    @property
    def narration_path(self) -> Path:
        """Return the narration record path, populated only for simulated runs."""
        return self.run_dir / "narration.json"

    @property
    def options_path(self) -> Path:
        """Return the recorded run options, written by every run since 7.3."""
        return self.run_dir / "generation_options.json"

    @property
    def brief_path(self) -> Path:
        """Return the structured brief a run was asked with, present only for brief runs."""
        return self.run_dir / "brief.json"

    def __fspath__(self) -> str:
        """Expose the run directory through the filesystem path protocol."""
        return str(self.run_dir)


class StoryGenerator:
    """Provide the stable public API for Stagecraft generation.

    The keywords mirror GenerationOptions field for field, and a test holds them in step: the
    console and the bot build this facade through `create_autospec(spec_set=True)`, so an
    explicit signature is what lets their tests reject an option the facade does not declare.
    """

    def __init__(
        self,
        provider,
        output_root: Path,
        *,
        narrative_guidance: bool = True,
        narrative_profile: NarrativeProfile | None = None,
        audio: bool = True,
        audio_voice: str = "",
        promise_ledger: bool = True,
        story_format: StoryFormat = StoryFormat.NARRATIVE,
        script_method: ScriptMethod = ScriptMethod.NATIVE,
        narrative_voice: NarrativeVoice = NarrativeVoice.OMNISCIENT,
        narrator: str = "",
        narration_tone: str = "",
        actor_memory: ActorMemory = ActorMemory.OWN,
        turns_per_beat: int = 8,
    ) -> None:
        """Configure a generator with its provider, output directory and run options."""
        self.provider = provider
        self.output_root = Path(output_root)
        self.options = GenerationOptions(
            narrative_guidance=narrative_guidance,
            narrative_profile=narrative_profile,
            audio=audio,
            audio_voice=audio_voice,
            promise_ledger=promise_ledger,
            story_format=story_format,
            script_method=script_method,
            narrative_voice=narrative_voice,
            narrator=narrator,
            narration_tone=narration_tone,
            actor_memory=actor_memory,
            turns_per_beat=turns_per_beat,
        )

    @classmethod
    def from_options(
        cls,
        provider,
        output_root: Path,
        options: GenerationOptions,
    ) -> StoryGenerator:
        """Build a generator from options a surface has already validated."""
        return cls(provider, output_root, **dict(options))

    def generate(
        self,
        request: StoryRequest | str | StoryBrief,
        on_progress: ProgressCallback | None = None,
        on_run_created: Callable[[Path], None] | None = None,
        on_event: PipelineEventCallback | None = None,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> StoryRun:
        """Generate one complete story and return its run handle.

        should_cancel is polled before every agent call; once it answers True the run stops
        with RunCancelledError (RUN_CANCELLED) and its artifacts record where it stopped. A
        surface must stop a run this way, never by raising from a callback.
        """
        pipeline = StoryPipeline(
            self.provider,
            self.output_root,
            options=self.options,
            on_progress=on_progress,
            on_run_created=on_run_created,
            on_event=on_event,
            should_cancel=should_cancel,
        )
        return StoryRun(pipeline.execute(request))
