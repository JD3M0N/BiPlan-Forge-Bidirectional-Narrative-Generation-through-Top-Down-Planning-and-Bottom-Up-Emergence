"""Stage-oriented orchestration for the Stagecraft story pipeline."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from asg_core import create_story_audio_sync

from .agents import (
    AnalystAgent,
)
from .brief import (
    StoryBrief,
)
from .formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from .options import GenerationOptions
from .planning.graph import (
    validate_story_plan,
)
from .planning.length import requested_profile
from .planning.profiles import PROFILE_LABELS, NarrativeProfile
from .planning.stages import PlanningStagesMixin
from .runtime.errors import (
    RunCancelledError,
    RunInterruptedError,
)
from .runtime.progress import PipelineEventCallback, ProgressCallback
from .runtime.provider import call_context
from .runtime.reporting import CHECKPOINT_STAGES, RunReportingMixin
from .runtime.storage import ArtifactRepository
from .schemas import (
    CharactersArtifact,
    PlayScript,
    PromiseLedger,
    StoryPlan,
    StoryRequest,
    WorldArtifact,
)
from .script.render import render_script
from .script.stages import ScriptStagesMixin
from .stage.metrics import SimulationMetrics, renarrated_metrics
from .stage.schemas import CastBible, PerformanceArtifact
from .stage.stages import SimulationStagesMixin
from .version import SUPPORTED_PIPELINE_VERSIONS
from .writing.assembly import assemble_story
from .writing.audit import story_metrics
from .writing.language import language_code, prompt_language, repair_mojibake
from .writing.localization import LocalizationMixin
from .writing.stages import WritingStagesMixin

T = TypeVar("T")

# The folder name of a run whose request could not be analyzed; the prompt goes to
# submitted_request.json instead of into the name.
UNANALYZED_TITLE = "peticion sin analizar"
# Read by the tests through this module: the stage order lives in runtime/reporting.py.
__all__ = ["CHECKPOINT_STAGES", "StoryPipeline", "UNANALYZED_TITLE"]

# What every reuse of a finished run freezes: the request and the plan it was drawn from.
_PLAN_ARTIFACTS = {
    "request.json": StoryRequest,
    "world.json": WorldArtifact,
    "characters.json": CharactersArtifact,
    "story_plan.json": StoryPlan,
}
# The options a performance was played with: a narration replay records the source's.
_PERFORMANCE_OPTIONS = (
    "narrative_profile",
    "actor_memory",
    "simulation_mode",
    "inventory",
    "turns_per_beat",
    "typed_clauses",
)
# The stages a narration replay inherits from its source as already done.
_PERFORMED_STAGES = (
    "analysis",
    "world",
    "characters",
    "planning",
    "drafting",
    "casting",
    "performance",
)


def _compatible_source(source: Path, *, simulated: bool) -> dict:
    """Read a source run's metadata, refusing one this code cannot reuse."""
    metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
    if (
        metadata.get("status") != "completed"
        or metadata.get("pipeline_version") not in SUPPORTED_PIPELINE_VERSIONS
        or (simulated and metadata.get("story_format") != StoryFormat.SIMULATED.value)
    ):
        kind = "simulated " if simulated else ""
        raise ValueError(f"the source must be a completed compatible {kind}run")
    return {**metadata, "_directory": str(source)}


def _frozen_artifacts(source: Path, frozen_types: dict) -> tuple[dict, dict]:
    """Read and validate a source run's frozen artifacts, keeping their exact bytes."""
    raw = {name: (source / name).read_bytes() for name in frozen_types}
    return raw, {name: model.model_validate_json(raw[name]) for name, model in frozen_types.items()}


def _source_ledger(source: Path) -> PromiseLedger | None:
    """Read a source run's promise ledger, or None when that run traced none."""
    path = source / "promise_ledger.json"
    return PromiseLedger.model_validate_json(path.read_bytes()) if path.is_file() else None


def _source_options(source: Path) -> dict:
    """Read the options a source run recorded, empty for a run older than 7.3."""
    try:
        return json.loads((source / "generation_options.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


class StoryPipeline(
    PlanningStagesMixin,
    WritingStagesMixin,
    ScriptStagesMixin,
    SimulationStagesMixin,
    LocalizationMixin,
    RunReportingMixin,
):
    """Execute one Stagecraft request through explicit, testable stages."""

    def __init__(
        self,
        provider,
        output_root: Path,
        *,
        options: GenerationOptions | None = None,
        on_progress: ProgressCallback | None = None,
        on_run_created: Callable[[Path], None] | None = None,
        on_event: PipelineEventCallback | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> None:
        """Store pipeline dependencies, the run's options and optional lifecycle callbacks."""
        self.provider = provider
        self.output_root = Path(output_root)
        self.options = options or GenerationOptions()
        self.on_progress = on_progress
        self.on_run_created = on_run_created
        self.on_event = on_event
        self.should_cancel = should_cancel
        # Set once the story is being published: a cancel that arrives then would discard a
        # finished story to save the audio step, so it is ignored.
        self._finishing = False
        # The structured brief a run was asked with, when it was asked with one.
        self.brief: StoryBrief | None = None
        # Warnings about the request found before analysis, when no repository exists yet.
        self._early_warnings: list[tuple[str, str]] = []
        self.progress = {"percent": 0, "stage": "analysis"}
        self.usage_start = 0
        self.repository: ArtifactRepository | None = None

    # The stages read their options under the names they had before GenerationOptions existed,
    # so the script and simulation mixins did not have to change when the options were gathered.

    @property
    def narrative_guidance(self) -> bool:
        """Say whether the plot-skeleton blueprint guides this run."""
        return self.options.narrative_guidance

    @property
    def promise_ledger(self) -> bool:
        """Say whether this run traces a promise ledger over its frozen plan."""
        return self.options.promise_ledger

    @property
    def narrative_profile(self) -> NarrativeProfile | None:
        """Return the profile the caller forced, or None to keep the analyst's inference."""
        return self.options.narrative_profile

    @property
    def audio(self) -> bool:
        """Say whether this run ends by narrating its story as audio."""
        return self.options.audio

    @property
    def story_format(self) -> StoryFormat:
        """Return the shape of the artifact this run delivers."""
        return self.options.story_format

    @property
    def script_method(self) -> ScriptMethod:
        """Return how a script run turns the plan into scenes."""
        return self.options.script_method

    @property
    def narrative_voice(self) -> NarrativeVoice:
        """Return the point of view a simulated run is narrated from."""
        return self.options.narrative_voice

    @property
    def actor_memory(self) -> ActorMemory:
        """Return whether each actor remembers only what it witnessed or everything public."""
        return self.options.actor_memory

    @property
    def inventory(self) -> bool:
        """Say whether the performance tracks and arbitrates physical objects."""
        return self.options.inventory

    @property
    def turns_per_beat(self) -> int:
        """Return how many turns a beat may take before the world closes it."""
        return self.options.turns_per_beat

    @property
    def _simulated(self) -> bool:
        """Say whether this run ends in a performance narrated from its own log."""
        return self.story_format is StoryFormat.SIMULATED

    @property
    def _stages_the_script(self) -> bool:
        """Say whether this run writes a native theater script before anything else happens.

        True for a native script run and for every simulated run: the simulation always stages
        the native script, because adapting prose into a script only to narrate prose again
        would run the same material through the model twice for no gain.
        """
        return self._simulated or (
            self.story_format is StoryFormat.SCRIPT and self.script_method is ScriptMethod.NATIVE
        )

    def _recorded_script_method(self) -> ScriptMethod | None:
        """Name the script method this run's metadata declares, or none when it has no script."""
        if self.story_format is StoryFormat.SCRIPT:
            return self.script_method
        if self._simulated:
            return ScriptMethod.NATIVE
        return None

    def execute(self, request: StoryRequest | str | StoryBrief) -> Path:
        """Run all story stages and return the completed run directory.

        A StoryBrief is composed into its prompt here and then analyzed like any other; the
        brief itself is kept as brief.json, and its cast is checked once the cast exists.
        """
        if isinstance(request, StoryBrief):
            self.brief = request
            request = request.to_prompt()
        elif isinstance(request, str):
            request = self._read_prompt(request)
        self.usage_start = len(getattr(self.provider, "usage_records", []))
        # Analysis names the run directory, so its repository cannot exist yet. A failure here
        # still gets one, or this would be the only stage that leaves no error_report.json.
        submitted = request
        try:
            request = self._analyze_request(submitted)
        except Exception as exc:
            self.repository = self._create_repository(self._fallback_title(submitted))
            self._flush_early_warnings()
            self._save_submitted_request(submitted)
            self._record_failure(exc)
            raise
        self.repository = self._create_repository(request.title)
        try:
            self._configure_provider_callbacks()
            self._flush_early_warnings()
            request = self._with_prompt_language(request)
            self._note_requested_profile(request)
            self._save_request(request)
            blueprint = self._build_blueprint(request)
            world = self._build_world(request)
            characters = self._build_characters(request, world, blueprint)
            plan = self._build_plan(request, world, characters, blueprint)
            ledger = self._build_promise_ledger(request, plan)
            if self._stages_the_script:
                play = self._write_script(request, world, characters, plan, ledger)
                self._save_script(request, plan, play)
                if self._simulated:
                    self._perform_and_narrate(request, world, characters, plan, play, ledger)
                else:
                    self._publish(render_script(play), "Guardando el guion", "Guion terminado")
                return self.repository.run_dir
            presentation, draft_bodies, draft = self._draft_chapters(
                request,
                world,
                characters,
                plan,
                ledger,
            )
            bodies = self._critique_and_revise(
                request,
                world,
                characters,
                plan,
                presentation,
                draft_bodies,
                draft,
                ledger,
            )
            story = assemble_story(plan, presentation, bodies)
            if self.story_format is StoryFormat.SCRIPT:
                play = self._adapt_story(
                    request, world, characters, plan, presentation, bodies, story, ledger
                )
                self._finalize_script(request, plan, play)
            else:
                self._finalize(request, plan, story)
            return self.repository.run_dir
        except Exception as exc:
            self._record_failure(exc)
            raise
        except BaseException as exc:
            # KeyboardInterrupt and SystemExit are not Exception, so without this branch an
            # abandoned run kept status "running" forever and StoryRun refused to open it.
            self._record_interruption(exc)
            raise
        finally:
            self._clear_provider_callbacks()

    def execute_from_plan(self, source_run: Path) -> Path:
        """Write a new run from the source's frozen plan, from its first writing stage on.

        A simulated run reuses the script and the cast too, and performs again. Since 7.17 a
        narrative run can reuse a plan as well, so two drafts from one plan differ only in how
        they were written: that is what makes a Top-Down arm readable with a handful of runs.
        """
        source = Path(source_run)
        if self._simulated:
            frozen_types = {
                **_PLAN_ARTIFACTS,
                "script.json": PlayScript,
                "cast_bible.json": CastBible,
            }
        elif self.story_format is StoryFormat.NARRATIVE:
            frozen_types = dict(_PLAN_ARTIFACTS)
        else:
            raise ValueError("plan reuse requires the narrative or simulated story format")
        metadata = _compatible_source(source, simulated=self._simulated)
        raw, frozen = _frozen_artifacts(source, frozen_types)
        request = frozen["request.json"]
        world = frozen["world.json"]
        characters = frozen["characters.json"]
        plan = frozen["story_plan.json"]
        validate_story_plan(plan, world, characters)
        ledger = _source_ledger(source)
        self.usage_start = len(getattr(self.provider, "usage_records", []))
        self.repository = self._create_repository(request.title)
        try:
            self._configure_provider_callbacks()
            self._save_frozen(metadata, raw, frozen, ledger, "plan")
            self.repository.metadata.narrative_profile = request.narrative_profile
            if self._simulated:
                for stage in ("analysis", "world", "characters", "planning", "drafting", "casting"):
                    self.repository.complete_stage(stage)
                play, bible = frozen["script.json"], frozen["cast_bible.json"]
                self._perform_and_narrate(request, world, characters, plan, play, ledger, bible)
                return self.repository.run_dir
            for stage in ("analysis", "world", "characters", "planning"):
                self.repository.complete_stage(stage)
            presentation, draft_bodies, draft = self._draft_chapters(
                request, world, characters, plan, ledger
            )
            bodies = self._critique_and_revise(
                request, world, characters, plan, presentation, draft_bodies, draft, ledger
            )
            self._finalize(request, plan, assemble_story(plan, presentation, bodies))
            return self.repository.run_dir
        except Exception as exc:
            self._record_failure(exc)
            raise
        except BaseException as exc:
            self._record_interruption(exc)
            raise
        finally:
            self._clear_provider_callbacks()

    def execute_from_performance(self, source_run: Path) -> Path:
        """Narrate a new run from the source's frozen performance, without performing again.

        A narration costs about a dozen calls and a performance about a hundred and thirty, and
        the performance is where the noise between two runs comes from. Narrating one log twice,
        one way and another, compares the two ways and nothing else (7.17).
        """
        if not self._simulated:
            raise ValueError("narration reuse requires the simulated story format")
        source = Path(source_run)
        metadata = _compatible_source(source, simulated=True)
        frozen_types = {
            **_PLAN_ARTIFACTS,
            "script.json": PlayScript,
            "cast_bible.json": CastBible,
            "performance.json": PerformanceArtifact,
            "simulation_metrics.json": SimulationMetrics,
        }
        raw, frozen = _frozen_artifacts(source, frozen_types)
        request = frozen["request.json"]
        characters = frozen["characters.json"]
        plan = frozen["story_plan.json"]
        play = frozen["script.json"]
        performance = frozen["performance.json"]
        ledger = _source_ledger(source)
        # What the performance was played with belongs to the source: only the narration may
        # differ, so the options this run records say so.
        recorded = _source_options(source)
        self.options = self.options.with_changes(
            **{name: recorded[name] for name in _PERFORMANCE_OPTIONS if name in recorded}
        )
        self.usage_start = len(getattr(self.provider, "usage_records", []))
        self.repository = self._create_repository(request.title)
        try:
            self._configure_provider_callbacks()
            self._save_frozen(metadata, raw, frozen, ledger, "performance")
            self.repository.metadata.narrative_profile = request.narrative_profile
            self.repository.metadata.stage_model = metadata.get("stage_model")
            for stage in _PERFORMED_STAGES:
                self.repository.complete_stage(stage)
            story, narration, fallbacks, narrated = self._narrate(
                request,
                characters,
                plan,
                play,
                performance,
                ledger,
                world=frozen["world.json"],
                bible=frozen["cast_bible.json"],
            )
            self._audit_performed_promises(ledger, performance, story)
            metrics = renarrated_metrics(
                frozen["simulation_metrics.json"], performance, story, fallbacks
            ).model_copy(update={"narrative_voice": narration.narrative_voice})
            self.repository.save_json("simulation_metrics.json", metrics)
            self.repository.save_json("story_metrics.json", story_metrics(request, narrated, story))
            self._publish(story, "Guardando la historia", "Historia renarrada terminada")
            return self.repository.run_dir
        except Exception as exc:
            self._record_failure(exc)
            raise
        except BaseException as exc:
            self._record_interruption(exc)
            raise
        finally:
            self._clear_provider_callbacks()

    def _save_frozen(self, metadata, raw, frozen, ledger, reused: str) -> None:
        """Copy a source run's frozen artifacts into this run, with their fingerprints."""
        assert self.repository is not None
        self.repository.save_data(
            "source_run.json",
            {
                "run_id": metadata["run_id"],
                "reused": reused,
                "frozen_sha256": {
                    name: hashlib.sha256(content).hexdigest() for name, content in raw.items()
                },
            },
        )
        for name, artifact in frozen.items():
            if name != "simulation_metrics.json":
                self.repository.save_json(name, artifact)
        if ledger is not None:
            self.repository.save_json("promise_ledger.json", ledger)
        source = Path(metadata["_directory"])
        for name in ("script_presentation.json", "script_promise_audit.json"):
            path = source / name
            if path.is_file():
                self.repository.save_data(name, json.loads(path.read_text(encoding="utf-8")))

    def _analyze_request(self, request: StoryRequest | str) -> StoryRequest:
        """Convert a free-form prompt into a validated story request."""
        self._notify(0, "analysis", "Analizando la solicitud")
        if isinstance(request, StoryRequest):
            return self._with_forced_profile(request)

        def analyze_request():
            """Analyze the bound free-form request into a story contract."""
            return AnalystAgent(self.provider).run(request)

        return self._with_forced_profile(self._call_agent("analyst", analyze_request))

    def _with_prompt_language(self, request: StoryRequest) -> StoryRequest:
        """Keep the language the prompt is plainly written in over the analyst's guess (7.15).

        Runs once the repository exists, since analysis is what names the run directory.
        """
        written = prompt_language(request.original_prompt)
        if not written or language_code(written) == language_code(request.language):
            return request
        warning = (
            f"[LANGUAGE_OVERRIDE] El análisis dio {request.language}; el prompt está en {written}."
        )
        assert self.repository is not None
        self.repository.add_warning(warning)
        self._emit("language_override", warning, stage="analysis")
        return request.model_copy(update={"language": written})

    def _read_prompt(self, prompt: str) -> str:
        """Repair a prompt's encoding and read a composed brief out of it (7.20).

        Both were lost in the 7.19 batch: Windows PowerShell handed every prompt over
        double-encoded, and the islands brief was pasted as a free prompt, so its cast and plot
        never reached the agents as canon.
        """
        repaired = repair_mojibake(prompt)
        if repaired != prompt:
            self._early_warnings.append(
                (
                    "prompt_encoding_repaired",
                    "[PROMPT_ENCODING_REPAIRED] El prompt llegó con la codificación rota "
                    "(UTF-8 leído como Windows-1252) y se reparó antes del análisis.",
                )
            )
        brief = StoryBrief.from_prompt(repaired) if self.brief is None else None
        if brief is not None:
            self.brief = brief
            self._early_warnings.append(
                (
                    "brief_from_prompt",
                    "[BRIEF_FROM_PROMPT] El prompt es una ficha: su reparto y su trama se tratan "
                    "como canon, igual que con --brief.",
                )
            )
        return repaired

    def _flush_early_warnings(self) -> None:
        """Record the warnings found before the run had a repository to hold them."""
        assert self.repository is not None
        for kind, warning in self._early_warnings:
            self.repository.add_warning(warning)
            self._emit(kind, warning, stage="analysis")
        self._early_warnings = []

    def _note_requested_profile(self, request: StoryRequest) -> None:
        """Say which profile the request's own length asked for, and warn when overridden.

        The 7.19 islands runs were forced Essential for a brief whose notes ask for a long story,
        and nothing in the run said so. A profile the request chose is only reported; a forced
        one that contradicts it is a warning the run keeps.
        """
        asked = requested_profile(request.original_prompt)
        if asked is None:
            return
        profile, reason = asked
        if self.narrative_profile is None or self.narrative_profile == profile:
            self._emit(
                "profile_from_request",
                f"[PROFILE_FROM_REQUEST] {PROFILE_LABELS[profile]}: la petición {reason}.",
                stage="analysis",
            )
            return
        warning = (
            f"[PROFILE_CONFLICT] La petición {reason}, que corresponde a "
            f"{PROFILE_LABELS[profile]}, pero el run se forzó en "
            f"{PROFILE_LABELS[self.narrative_profile]}."
        )
        assert self.repository is not None
        self.repository.add_warning(warning)
        self._emit("profile_conflict", warning, stage="analysis")

    def _with_forced_profile(self, request: StoryRequest) -> StoryRequest:
        """Apply the caller's explicit profile, which outranks any prompt-derived choice."""
        if self.narrative_profile is None:
            return request
        return request.model_copy(update={"narrative_profile": self.narrative_profile})

    @staticmethod
    def _fallback_title(request: StoryRequest | str) -> str:
        """Name a run whose analysis failed, so its failure still lands somewhere readable.

        A raw prompt made a poor name - 060405 was called after the first sixty characters of
        its prompt, cut mid-word - so an unanalyzed request gets a neutral one, and the prompt
        itself is kept in submitted_request.json.
        """
        return request.title if isinstance(request, StoryRequest) else UNANALYZED_TITLE

    def _save_submitted_request(self, request: StoryRequest | str) -> None:
        """Keep what was asked for when analysis failed, so the run can be understood."""
        assert self.repository is not None
        prompt = request.original_prompt if isinstance(request, StoryRequest) else request
        profile = self.narrative_profile
        self.repository.save_data(
            "submitted_request.json",
            {
                "prompt": prompt,
                "narrative_profile": profile.value if profile else None,
                "story_format": self.story_format.value,
            },
        )
        if profile:
            self.repository.metadata.narrative_profile = profile

    def _create_repository(self, title: str) -> ArtifactRepository:
        """Create the run repository and attach artifact event reporting."""
        # A routed provider names the performance's own model; a single one names none.
        stage_model = getattr(self.provider, "stage_model_name", None)
        repository = ArtifactRepository(
            self.output_root,
            self.provider.model_name,
            title,
            on_artifact=self._report_artifact,
            story_format=self.story_format,
            script_method=self._recorded_script_method(),
            narrative_voice=self.narrative_voice if self._simulated else None,
            actor_memory=self.actor_memory if self._simulated else None,
            stage_model=stage_model if self._simulated else None,
            prose_model=getattr(self.provider, "prose_model_name", None),
        )
        # Every axis a run can differ on, including the ledger, guidance and audio switches
        # that no other artifact records (7.3). Written first, so a failed run keeps it too.
        repository.save_json("generation_options.json", self.options)
        if self.brief is not None:
            repository.save_json("brief.json", self.brief)
        if self.on_run_created:
            self.on_run_created(repository.run_dir)
        for record in list(getattr(self.provider, "usage_records", []))[self.usage_start :]:
            repository.append_llm_call(record)
        return repository

    def _save_request(self, request: StoryRequest) -> None:
        """Persist the analyzed request and complete the analysis stage."""
        assert self.repository is not None
        self.repository.save_json("request.json", request)
        self.repository.metadata.narrative_profile = request.narrative_profile
        self.repository.complete_stage("analysis")

    def _publish(self, rendered: str, saving_message: str, done_message: str) -> None:
        """Write the final artifact, close the run, and report completion.

        Shared by the narrative story and the theater-script tails, so both formats leave the
        run in the same completed shape: story.md, optional audio,
        usage, and a completed status.
        """
        assert self.repository is not None
        self._finishing = True
        self._notify(98, "story", saving_message)
        self.repository.save_text("story.md", rendered)
        self.repository.complete_stage("story")
        self._create_audio()
        self._save_usage()
        self.repository.complete()
        self._notify(100, "completed", done_message)

    def _create_audio(self) -> None:
        """Create optional narration without invalidating a completed story."""
        assert self.repository is not None
        if not self.audio:
            return
        self._notify(99, "audio", "Generando narración de la historia")
        # Narration never calls the model, so no error reaching here justifies discarding a
        # story that is already written: every failure degrades to a warning, including one
        # raised while registering the artifact.
        try:
            story_path = self.repository.run_dir / "story.md"
            # Only a chosen voice is passed on: without one, the call is the one every run made
            # before 7.3, and the language of the story picks the voice.
            if self.options.audio_voice:
                create_story_audio_sync(story_path, voice=self.options.audio_voice)
            else:
                create_story_audio_sync(story_path)
            self.repository.register_existing("story.mp3")
            self.repository.complete_stage("audio")
        except Exception as exc:
            warning = (
                "[AUDIO_GENERATION_FAILED] No se pudo crear story.mp3 "
                f"({type(exc).__name__}); story.md permanece válido."
            )
            self.repository.add_warning(warning)
            self._emit("audio_skipped", warning, stage="audio")
        try:
            if (self.repository.run_dir / "audio.json").is_file():
                self.repository.register_existing("audio.json")
        except OSError:
            pass

    def _record_failure(self, error: Exception) -> None:
        """Persist a failed pipeline outcome before re-raising the error.

        The stage recorded is the pipeline's, where the run stopped; the error's own stage is
        the component that raised it and travels in the report's details.
        """
        assert self.repository is not None
        stage = self.progress["stage"]
        summary = getattr(error, "summary", type(error).__name__)
        self._emit("pipeline_failed", f"fallo la etapa {stage}: {summary}", stage=stage)
        self._save_usage()
        self.repository.fail(error, stage=stage)

    def _record_interruption(self, error: BaseException) -> None:
        """Close a run the process abandoned, so no run is left stranded in "running"."""
        assert self.repository is not None
        stage = self.progress["stage"]
        interrupted = RunInterruptedError(
            "La generación se interrumpió antes de terminar.",
            details={"exception_type": type(error).__name__},
            recommendations=["Vuelve a lanzar la generación: esta ejecución quedó incompleta."],
        )
        interrupted.stage = stage
        self._emit("pipeline_interrupted", f"se interrumpio la etapa {stage}", stage=stage)
        self._save_usage()
        self.repository.fail(interrupted, stage=stage)

    def _call_agent(self, name: str, function: Callable[[], T]) -> T:
        """Emit an agent event and run the agent, tagging its model calls with stage and agent."""
        self._checkpoint()
        self._emit("agent_called", f"se llamó al agente {name}", stage=self.progress["stage"])
        with call_context(self.progress["stage"], name):
            return function()

    def _checkpoint(self) -> None:
        """Stop the run here when its caller asked to, before another model call is spent.

        Every agent call passes through here - the actors, the director and the narrator
        included - so a cancel waits for one call at most. The check lives in the pipeline
        rather than in a callback because a callback can fire inside the provider's retry loop,
        which rewraps any exception as a degradable provider error.
        """
        if self.should_cancel is None or self._finishing or not self.should_cancel():
            return
        raise RunCancelledError(
            "La generación se canceló a petición de quien la lanzó.",
            recommendations=["Vuelve a lanzarla cuando quieras: esta ejecución quedó incompleta."],
        )
