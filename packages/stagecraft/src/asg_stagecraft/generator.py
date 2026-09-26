"""Public facade for Stagecraft story generation."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
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

    def __fspath__(self) -> str:
        """Expose the run directory through the filesystem path protocol."""
        return str(self.run_dir)


class StoryGenerator:
    """Provide the stable public API for Stagecraft generation."""

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
        narrative_voice: NarrativeVoice = NarrativeVoice.OMNISCIENT,
        actor_memory: ActorMemory = ActorMemory.OWN,
        turns_per_beat: int = 8,
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
        self.narrative_voice = narrative_voice
        self.actor_memory = actor_memory
        self.turns_per_beat = turns_per_beat

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
            narrative_voice=self.narrative_voice,
            actor_memory=self.actor_memory,
            turns_per_beat=self.turns_per_beat,
        )
        return StoryRun(pipeline.execute(request))
