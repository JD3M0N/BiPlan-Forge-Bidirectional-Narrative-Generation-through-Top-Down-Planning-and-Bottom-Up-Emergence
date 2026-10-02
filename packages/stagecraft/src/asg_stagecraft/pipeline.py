"""Stage-oriented orchestration for the Stagecraft story pipeline."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from asg_core import create_story_audio_sync
from asg_evaluation import create_evaluation_template

from .agents import (
    AnalystAgent,
    CharacterDesignerAgent,
    DrafterAgent,
    DramaCriticAgent,
    PlanCriticAgent,
    PlotPlannerAgent,
    PromiseLedgerAgent,
    StoryArchitectAgent,
    WorldBuilderAgent,
    WriterAgent,
)
from .brief import StoryBrief, cast_repair_feedback, missing_cast
from .formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from .options import GenerationOptions
from .planning.graph import (
    materialize_plan,
    relevant_prior_events,
    validate_profile_structure,
    validate_story_plan,
)
from .planning.profiles import NarrativeProfile
from .planning.promise_brief import critic_obligations, event_index, rendered_ledger
from .planning.promises import materialize_ledger
from .planning.repair import repair_guidance
from .runtime.errors import (
    NON_DEGRADABLE_ERRORS,
    PlotValidationError,
    RunCancelledError,
    RunInterruptedError,
)
from .runtime.progress import PipelineEvent, PipelineEventCallback, ProgressCallback, ProgressUpdate
from .runtime.provider import COUNT_TOKENS_OPERATION, call_context
from .runtime.storage import ArtifactRepository
from .schemas import (
    ChapterPlan,
    ChapterRevisionAttempt,
    ChapterRevisionResult,
    CharacterProfile,
    CharactersArtifact,
    LLMUsageArtifact,
    NarrativeBlueprint,
    PlayScript,
    PlotEvent,
    PromiseAuditArtifact,
    PromiseAuditEntry,
    PromiseCheck,
    PromiseLedger,
    PromiseLedgerDraft,
    RevisionNote,
    RevisionReport,
    StoryPlan,
    StoryPlanDraft,
    StoryPresentation,
    StoryRequest,
    StoryReview,
    WorldArtifact,
)
from .script.render import render_script
from .script.stages import ScriptStagesMixin
from .stage.schemas import CastBible
from .stage.stages import SimulationStagesMixin
from .version import SUPPORTED_PIPELINE_VERSIONS
from .writing.acceptance import writer_candidate_issue, writer_fallback_warning
from .writing.assembly import assemble_story
from .writing.audit import story_metrics, word_count
from .writing.craft_evidence import craft_evidence

T = TypeVar("T")

# Canonical order of pipeline checkpoint stages, shared by every _notify/complete_stage
# pair below; "rate_limit" is intentionally excluded (see _notify).
CHECKPOINT_STAGES = (
    "analysis",
    "architecture",
    "world",
    "characters",
    "planning",
    "plan_review",
    "promises",
    "drafting",
    "critique",
    "revision",
    "adaptation",
    # The hybrid stages of a simulated run: the cast bible, the props when the inventory is on,
    # the performance the actors improvise from the frozen script, and the prose narrated from
    # its log.
    "casting",
    "props",
    "performance",
    "narration",
    "story",
    "audio",
)

# In a simulated run the script is the director's book rather than the deliverable, so every
# stage up to and including the script's own revision is compressed into the first half of the
# progress range and the performance and narration own the rest.
PRE_PERFORMANCE_CEILING = 48
PRE_PERFORMANCE_STAGES = frozenset(CHECKPOINT_STAGES[: CHECKPOINT_STAGES.index("casting")])

# The folder name of a run whose request could not be analyzed; the prompt goes to
# submitted_request.json instead of into the name.
UNANALYZED_TITLE = "peticion sin analizar"

# Planning attempts allowed per narrative profile. Expansive carries the strictest structural
# contract (a causal branch followed by a causal join), so it gets one extra repair attempt.
DEFAULT_PLAN_ATTEMPTS = 3
PLAN_ATTEMPTS_BY_PROFILE: dict[NarrativeProfile, int] = {
    NarrativeProfile.EXPANSIVE: 4,
}

# The promise ledger annotates a plan that is already valid, so a rejected candidate has far less
# to repair than a rejected plan: one repair round is enough, and the stage degrades rather than
# spending more of the quota on prose guidance the story can do without.
PROMISE_ATTEMPTS = 2


class StoryPipeline(ScriptStagesMixin, SimulationStagesMixin):
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
        self.usage_start = len(getattr(self.provider, "usage_records", []))
        # Analysis names the run directory, so its repository cannot exist yet. A failure here
        # still gets one, or this would be the only stage that leaves no error_report.json.
        submitted = request
        try:
            request = self._analyze_request(submitted)
        except Exception as exc:
            self.repository = self._create_repository(self._fallback_title(submitted))
            self._save_submitted_request(submitted)
            self._record_failure(exc)
            raise
        self.repository = self._create_repository(request.title)
        try:
            self._configure_provider_callbacks()
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
        """Perform a new run from the source's frozen request, plan, script and cast."""
        if not self._simulated:
            raise ValueError("plan reuse requires the simulated story format")
        source = Path(source_run)
        metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
        if (
            metadata.get("status") != "completed"
            or metadata.get("story_format") != StoryFormat.SIMULATED.value
            or metadata.get("pipeline_version") not in SUPPORTED_PIPELINE_VERSIONS
        ):
            raise ValueError("plan source must be a completed compatible simulated run")
        frozen_types = {
            "request.json": StoryRequest,
            "world.json": WorldArtifact,
            "characters.json": CharactersArtifact,
            "story_plan.json": StoryPlan,
            "script.json": PlayScript,
            "cast_bible.json": CastBible,
        }
        raw = {name: (source / name).read_bytes() for name in frozen_types}
        frozen = {
            name: model.model_validate_json(raw[name]) for name, model in frozen_types.items()
        }
        request = frozen["request.json"]
        world = frozen["world.json"]
        characters = frozen["characters.json"]
        plan = frozen["story_plan.json"]
        play = frozen["script.json"]
        bible = frozen["cast_bible.json"]
        validate_story_plan(plan, world, characters)
        ledger_path = source / "promise_ledger.json"
        ledger = (
            PromiseLedger.model_validate_json(ledger_path.read_bytes())
            if ledger_path.is_file()
            else None
        )
        self.usage_start = len(getattr(self.provider, "usage_records", []))
        self.repository = self._create_repository(request.title)
        try:
            self._configure_provider_callbacks()
            self.repository.save_data(
                "source_run.json",
                {
                    "run_id": metadata["run_id"],
                    "frozen_sha256": {
                        name: hashlib.sha256(content).hexdigest() for name, content in raw.items()
                    },
                },
            )
            for name, artifact in frozen.items():
                self.repository.save_json(name, artifact)
            if ledger is not None:
                self.repository.save_json("promise_ledger.json", ledger)
            for name in ("script_presentation.json", "script_promise_audit.json"):
                path = source / name
                if path.is_file():
                    self.repository.save_data(name, json.loads(path.read_text(encoding="utf-8")))
            self.repository.metadata.narrative_profile = request.narrative_profile
            for stage in ("analysis", "world", "characters", "planning", "drafting", "casting"):
                self.repository.complete_stage(stage)
            self._perform_and_narrate(request, world, characters, plan, play, ledger, bible)
            return self.repository.run_dir
        except Exception as exc:
            self._record_failure(exc)
            raise
        except BaseException as exc:
            self._record_interruption(exc)
            raise
        finally:
            self._clear_provider_callbacks()

    def _analyze_request(self, request: StoryRequest | str) -> StoryRequest:
        """Convert a free-form prompt into a validated story request."""
        self._notify(0, "analysis", "Analizando la solicitud")
        if isinstance(request, StoryRequest):
            return self._with_forced_profile(request)

        def analyze_request():
            """Analyze the bound free-form request into a story contract."""
            return AnalystAgent(self.provider).run(request)

        return self._with_forced_profile(self._call_agent("analyst", analyze_request))

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

    def _report_artifact(self, filename: str, created: bool) -> None:
        """Emit a structured event when an artifact is written."""
        self._emit(
            "artifact_created" if created else "artifact_updated",
            f"artefacto {filename} {'creado' if created else 'actualizado'}",
            stage=self.progress["stage"],
            artifact=filename,
        )

    def _report_wait(self, seconds: int, reason: str) -> None:
        """Report provider quota waits through the pipeline progress channel."""
        self._notify(
            self.progress["percent"],
            "rate_limit",
            f"Esperando cuota: {seconds}s ({reason})",
        )

    def _configure_provider_callbacks(self) -> None:
        """Route provider quota and usage events into pipeline callbacks."""
        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = self._report_wait
        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = self._record_usage

    def _clear_provider_callbacks(self) -> None:
        """Detach per-run provider callbacks after completion or failure."""
        if hasattr(self.provider, "usage_callback"):
            self.provider.usage_callback = None
        if hasattr(self.provider, "wait_callback"):
            self.provider.wait_callback = None

    def _record_usage(self, record) -> None:
        """Persist one provider usage record and refresh the aggregate."""
        assert self.repository is not None
        self.repository.append_llm_call(record)
        self._save_usage()

    def _usage_artifact(self) -> LLMUsageArtifact:
        """Aggregate this run's provider usage into logical calls, attempts and auxiliaries.

        A call is every attempt sharing one call_id, and it failed when its last attempt did.
        Before 7.2 each failed attempt counted as a failed call and token counts as calls.
        """
        records = list(getattr(self.provider, "usage_records", []))[self.usage_start :]
        requests = [item for item in records if item.operation != COUNT_TOKENS_OPERATION]
        last_attempt = {item.call_id: item for item in requests}
        return LLMUsageArtifact(
            records=records,
            calls=len(last_attempt),
            failed_calls=sum(item.status == "failed" for item in last_attempt.values()),
            attempts=len(requests),
            failed_attempts=sum(item.status == "failed" for item in requests),
            auxiliary_calls=len(records) - len(requests),
            total_tokens=sum(item.total_tokens for item in records),
            total_wait_seconds=sum(item.wait_seconds for item in records),
        )

    def _save_usage(self) -> None:
        """Write the current aggregate LLM usage artifact."""
        assert self.repository is not None
        self.repository.save_json("llm_usage.json", self._usage_artifact())

    def _save_request(self, request: StoryRequest) -> None:
        """Persist the analyzed request and complete the analysis stage."""
        assert self.repository is not None
        self.repository.save_json("request.json", request)
        self.repository.metadata.narrative_profile = request.narrative_profile
        self.repository.complete_stage("analysis")

    def _build_blueprint(self, request: StoryRequest) -> NarrativeBlueprint | None:
        """Propose optional structural inspiration without ever failing the run."""
        assert self.repository is not None
        if not self.narrative_guidance:
            return None
        self._notify(6, "architecture", "Eligiendo el esqueleto narrativo")

        def build_blueprint():
            """Read the bound request against the plot skeleton catalog."""
            return StoryArchitectAgent(self.provider).run(request)

        try:
            blueprint = self._call_agent("architect", build_blueprint)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception:
            warning = "No se pudo trazar el esqueleto narrativo; la historia continua sin esa guia."
            self.repository.add_warning(warning)
            self._emit("architecture_skipped", warning, stage="architecture")
            return None
        self.repository.save_json("narrative_blueprint.json", blueprint)
        self.repository.complete_stage("architecture")
        return blueprint

    def _build_world(self, request: StoryRequest) -> WorldArtifact:
        """Generate and persist the story world artifact."""
        assert self.repository is not None
        self._notify(12, "world", "Construyendo el mundo")

        def build_world():
            """Generate the world for the bound story request."""
            return WorldBuilderAgent(self.provider).run(request)

        world = self._call_agent("world", build_world)
        self.repository.save_json("world.json", world)
        self.repository.complete_stage("world")
        return world

    def _build_characters(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        blueprint: NarrativeBlueprint | None = None,
    ) -> CharactersArtifact:
        """Generate and persist the story character artifact."""
        assert self.repository is not None
        self._notify(25, "characters", "Diseñando los personajes")

        def build_characters(feedback: str = ""):
            """Generate characters for the bound request and world."""
            return CharacterDesignerAgent(self.provider).run(request, world, blueprint, feedback)

        characters = self._call_agent("characters", build_characters)
        if self.brief is not None and self.brief.cast:
            characters = self._keep_declared_cast(characters, build_characters)
        self.repository.save_json("characters.json", characters)
        self.repository.complete_stage("characters")
        return characters

    def _keep_declared_cast(
        self,
        characters: CharactersArtifact,
        build_characters: Callable[[str], CharactersArtifact],
    ) -> CharactersArtifact:
        """Ask once more for any character the brief declared and the cast left out.

        One repair is enough to be worth it: losing the character a story was meant to be told
        from would cost the whole run, and the repair costs one call in its first minute. What
        is still missing afterwards is reported, not fought over.
        """
        assert self.repository is not None and self.brief is not None
        missing = missing_cast(self.brief, characters)
        if not missing:
            return characters
        self.repository.save_json("characters/attempt-001.json", characters)
        feedback = cast_repair_feedback(missing)
        characters = self._call_agent("characters", lambda: build_characters(feedback))
        still = missing_cast(self.brief, characters)
        if still:
            names = ", ".join(member.name for member in still)
            warning = f"[BRIEF_CAST_MISSING] El reparto no incluye: {names}."
            self.repository.add_warning(warning)
            self._emit("brief_cast_missing", warning, stage="characters")
        return characters

    def _build_plan(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        blueprint: NarrativeBlueprint | None = None,
    ) -> StoryPlan:
        """Generate, validate, critique, and optionally refine the story plan."""
        assert self.repository is not None
        self._notify(38, "planning", "Planificando capítulos y eventos")
        feedback = ""
        validation_errors: list[str] = []
        plan: StoryPlan | None = None
        attempts = PLAN_ATTEMPTS_BY_PROFILE.get(request.narrative_profile, DEFAULT_PLAN_ATTEMPTS)
        for attempt in range(1, attempts + 1):

            def generate_plan(feedback_snapshot: str = feedback):
                """Generate one plan candidate with feedback bound to this attempt."""
                return PlotPlannerAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    feedback_snapshot,
                    blueprint=blueprint,
                )

            draft = self._call_agent(
                "plot_planner",
                generate_plan,
            )
            try:
                plan = materialize_plan(draft, world, characters)
                validate_profile_structure(plan, request.narrative_profile)
            except ValueError as exc:
                plan = None
                feedback = self._record_rejected_plan(
                    draft,
                    attempt,
                    exc,
                    validation_errors,
                    request.narrative_profile,
                )
                continue
            break
        if plan is None:
            raise PlotValidationError(
                f"No se obtuvo un DAG de eventos válido después de {attempts} intentos.",
                details={"attempts": attempts, "validation_errors": validation_errors},
                recommendations=["Revisa los intentos guardados bajo planning/."],
            )
        self.repository.complete_stage("planning")
        plan = self._critique_plan(request, world, characters, plan, blueprint)
        self._persist_plan(plan, request, world, characters)
        return plan

    def _persist_plan(
        self,
        plan: StoryPlan,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
    ) -> None:
        """Revalidate the plan at its single write boundary before it becomes the run contract."""
        assert self.repository is not None
        try:
            validate_story_plan(plan, world, characters)
            validate_profile_structure(plan, request.narrative_profile)
        except ValueError as exc:
            issue = str(exc).strip() or type(exc).__name__
            raise PlotValidationError(
                "El plan que iba a guardarse no cumple su contrato estructural.",
                details={"stage": "planning", "issue": issue},
                recommendations=[
                    "Vuelve a generar la historia; no se guardó ningún plan inválido."
                ],
            ) from exc
        self.repository.save_json("story_plan.json", plan)

    def _critique_plan(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        original_plan: StoryPlan,
        blueprint: NarrativeBlueprint | None = None,
    ) -> StoryPlan:
        """Apply one bounded plan-critique round without risking a valid plan."""
        assert self.repository is not None
        self._notify(46, "plan_review", "Revisando la calidad dramática del plan")
        try:

            def critique_plan():
                """Critique the bound validated plan."""
                return PlanCriticAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    original_plan,
                )

            review = self._call_agent("plan_critic", critique_plan)
            self.repository.save_json("plan_review.json", review)
            self._validate_note_references(review.notes, original_plan)
            self.repository.complete_stage("plan_review")
            if review.approved:
                return original_plan

            def refine_plan():
                """Return one complete plan replacement guided by the critique."""
                return PlotPlannerAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    plan_review=review,
                    blueprint=blueprint,
                )

            candidate = self._call_agent("plot_planner", refine_plan)
            self.repository.save_json("planning/refined-candidate.json", candidate)
            try:
                refined = materialize_plan(candidate, world, characters)
                validate_profile_structure(refined, request.narrative_profile)
            except ValueError as exc:
                issue = str(exc).strip() or type(exc).__name__
                self.repository.save_data(
                    "planning/refined-candidate-validation.json",
                    {"issue": issue},
                )
                warning = (
                    "La revisión del plan produjo un reemplazo estructuralmente inválido; "
                    "se conservó el primer plan válido."
                )
                self.repository.add_warning(warning)
                self._emit("plan_refinement_fallback", warning, stage="plan_review")
                return original_plan
            self._emit("plan_refined", "plan refinado tras la crítica", stage="plan_review")
            return refined
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            warning = (
                "La crítica del plan no pudo completarse; se conservó el primer plan "
                f"estructuralmente válido ({type(exc).__name__})."
            )
            self.repository.add_warning(warning)
            self._emit("plan_review_fallback", warning, stage="plan_review")
            self.repository.complete_stage("plan_review")
            return original_plan

    def _record_rejected_plan(
        self,
        draft: StoryPlanDraft,
        attempt: int,
        error: ValueError,
        validation_errors: list[str],
        profile: NarrativeProfile,
    ) -> str:
        """Persist one rejected plan and return feedback for its replacement."""
        assert self.repository is not None
        issue = str(error).strip() or type(error).__name__
        validation_errors.append(issue)
        prefix = f"planning/attempt-{attempt:03d}"
        self.repository.save_json(f"{prefix}.json", draft)
        self.repository.save_data(
            f"{prefix}-validation.json",
            {"attempt": attempt, "issue": issue},
        )
        self._emit(
            "plan_rejected",
            f"plan rechazado: {issue}",
            stage="planning",
            attempt=attempt,
        )
        # `issue` feeds the model's repair prompt, so it stays in English like the rest of
        # this contract; user-facing warnings and progress messages elsewhere are Spanish.
        return (
            "\n\nSTRUCTURAL REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT PLAN. "
            f"Fix this structural error: {issue}. "
            f"{repair_guidance(draft, issue, profile)}"
            f"REJECTED CANDIDATE:\n{draft.model_dump_json(indent=2)}"
        )

    def _build_promise_ledger(
        self,
        request: StoryRequest,
        plan: StoryPlan,
    ) -> PromiseLedger | None:
        """Draw the promise contract over the frozen plan, or let the story continue without it.

        The ledger changes how the plan is rendered, never what it contains, so losing it costs
        prose guidance and nothing else. That is why this stage degrades like the architect
        instead of aborting like planning.
        """
        assert self.repository is not None
        if not self.promise_ledger:
            return None
        self._notify(49, "promises", "Trazando las promesas de la historia")
        try:
            ledger = self._attempt_promise_ledger(request, plan)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception:
            ledger = None
        if ledger is None:
            warning = "No se pudo trazar el contrato de promesas; la historia continua sin el."
            self.repository.add_warning(warning)
            self._emit("promises_skipped", warning, stage="promises")
            return None
        self.repository.save_json("promise_ledger.json", ledger)
        self.repository.complete_stage("promises")
        return ledger

    def _attempt_promise_ledger(
        self,
        request: StoryRequest,
        plan: StoryPlan,
    ) -> PromiseLedger | None:
        """Run the bounded repair loop and return the first ledger that validates."""
        feedback = ""
        for attempt in range(1, PROMISE_ATTEMPTS + 1):

            def draw_ledger(feedback_snapshot: str = feedback):
                """Draw one ledger candidate with feedback bound to this attempt."""
                return PromiseLedgerAgent(self.provider).run(request, plan, feedback_snapshot)

            draft = self._call_agent("promise_ledger", draw_ledger)
            try:
                ledger = materialize_ledger(draft, plan, request.narrative_profile)
            except ValueError as exc:
                feedback = self._record_rejected_ledger(draft, attempt, exc, plan)
                continue
            return rendered_ledger(ledger, plan)
        return None

    def _record_rejected_ledger(
        self,
        draft: PromiseLedgerDraft,
        attempt: int,
        error: ValueError,
        plan: StoryPlan,
    ) -> str:
        """Persist one rejected ledger and build the repair block reinjected verbatim."""
        assert self.repository is not None
        issue = str(error).strip() or type(error).__name__
        self.repository.save_data(
            f"promises/attempt-{attempt:03d}.json",
            {"attempt": attempt, "issue": issue, "ledger": draft.model_dump(mode="json")},
        )
        return (
            "\n\nLEDGER REPAIR REQUIRED. RETURN A COMPLETE REPLACEMENT LEDGER. "
            f"The previous ledger was rejected: {issue}. The storyline stays frozen: repair the "
            "ledger, never the plan, and anchor every beat to one of these event IDs.\n"
            f"{event_index(plan)}"
        )

    @staticmethod
    def _promise_brief(ledger: PromiseLedger | None, chapter_id: str) -> str:
        """Return what one chapter owes the reader, or nothing when it owes nothing."""
        return ledger.chapter_blocks.get(chapter_id, "") if ledger else ""

    def _draft_chapters(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        ledger: PromiseLedger | None = None,
    ) -> tuple[StoryPresentation, list[str], str]:
        """Use Drafter to localize titles and create the first story."""
        assert self.repository is not None
        drafter = DrafterAgent(self.provider)

        def create_presentation():
            """Create localized story and chapter titles."""
            return drafter.presentation(request, plan)

        presentation = self._call_agent("drafter", create_presentation)
        self._validate_presentation(plan, presentation)
        self.repository.save_json("draft_presentation.json", presentation)
        event_by_id = {item.id: item for item in plan.events}
        bodies: list[str] = []
        for index, chapter in enumerate(plan.chapters, 1):
            self._notify_draft_chapter(index, len(plan.chapters))
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            history = relevant_prior_events(plan, {event.id for event in events})
            character_ids = {item for event in events for item in event.character_ids}
            relevant = [item for item in characters.characters if item.id in character_ids]

            def draft_chapter(
                character_snapshot=relevant or characters.characters,
                chapter_snapshot=chapter,
                event_snapshot=events,
                history_snapshot=history,
                previous_body: str = bodies[-1] if bodies else "",
                brief: str = self._promise_brief(ledger, chapter.id),
            ):
                """Draft one chapter with loop values bound to this iteration."""
                return drafter.run(
                    request,
                    world,
                    character_snapshot,
                    plan,
                    presentation,
                    chapter_snapshot,
                    event_snapshot,
                    history_snapshot,
                    previous_body,
                    brief,
                )

            body = self._call_agent("drafter", draft_chapter).strip()
            self.repository.save_text(f"chapters/chapter-{index:03d}.md", body)
            bodies.append(body)
        self.repository.complete_stage("drafting")
        draft = assemble_story(plan, presentation, bodies)
        self.repository.save_text("draft.md", draft)
        return presentation, bodies, draft

    @staticmethod
    def _validate_presentation(plan: StoryPlan, presentation: StoryPresentation) -> None:
        """Require one localized title for every canonical chapter, in order."""
        expected = [chapter.id for chapter in plan.chapters]
        received = [chapter.chapter_id for chapter in presentation.chapters]
        if received != expected:
            raise ValueError("localized presentation must follow the canonical chapter order")

    def _notify_draft_chapter(self, index: int, total: int) -> None:
        """Report progress for the chapter currently being drafted."""
        percent = 52 + (index - 1) * 24 // total
        self._notify(
            percent,
            "drafting",
            f"Redactando borrador del capítulo {index} de {total}",
            index,
            total,
        )

    def _critique_and_revise(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        presentation: StoryPresentation,
        draft_bodies: list[str],
        draft: str,
        ledger: PromiseLedger | None = None,
    ) -> list[str]:
        """Critique the complete draft, then let Writer revise chapter by chapter.

        Returns the final per-chapter bodies, not the assembled story: execute() assembles
        them, so a script run's adapter can reach the same bodies without reparsing Markdown.
        """
        assert self.repository is not None
        self._notify(78, "critique", "Analizando el drama del borrador completo")
        evidence = craft_evidence(plan.chapters, draft_bodies)
        self.repository.save_json("craft_evidence.json", evidence)
        obligations = critic_obligations(ledger)
        try:

            def critique_story():
                """Critique the bound complete story draft."""
                return DramaCriticAgent(self.provider).run(
                    request,
                    world,
                    characters,
                    plan,
                    presentation,
                    draft,
                    evidence.prompt_block,
                    obligations,
                )

            review = self._call_agent("drama_critic", critique_story)
            self.repository.save_json("review.json", review)
            self._validate_note_references(review.notes, plan)
            self._audit_promises(ledger, review)
            self.repository.complete_stage("critique")
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            warning = (
                "La crítica dramática no pudo completarse; se entregó el borrador "
                f"por capítulos ({type(exc).__name__})."
            )
            self.repository.add_warning(warning)
            self._emit("quality_fallback", warning, stage=self.progress["stage"])
            return draft_bodies
        return self._revise_chapters(
            request,
            characters,
            plan,
            presentation,
            draft_bodies,
            review,
            ledger,
        )

    def _audit_promises(self, ledger: PromiseLedger | None, review: StoryReview) -> None:
        """Cross the ledger with the critic's verdicts and record what the story delivered.

        A promise the critic never judged counts as broken. Silence is not a pass: the whole
        point of the ledger is that every expectation the story opened gets an answer, and an
        unanswered question about one is exactly what the audit exists to surface.
        """
        assert self.repository is not None
        if ledger is None:
            return
        checks = {check.promise_id: check for check in review.promise_checks}
        entries = [
            self._promise_entry(promise, checks.get(promise.id), ledger)
            for promise in ledger.promises
        ]
        verdicts = Counter(entry.verdict for entry in entries)
        self.repository.save_json(
            "promise_audit.json",
            PromiseAuditArtifact(
                promises=len(entries),
                fulfilled=verdicts["fulfilled"],
                weak=verdicts["weak"],
                broken=verdicts["broken"],
                fulfilled_ratio=round(verdicts["fulfilled"] / len(entries), 4) if entries else 0.0,
                entries=entries,
            ),
        )

    @staticmethod
    def _promise_entry(
        promise,
        check: PromiseCheck | None,
        ledger: PromiseLedger,
    ) -> PromiseAuditEntry:
        """Pair one promise of the ledger with the verdict the critic returned for it."""
        return PromiseAuditEntry(
            promise_id=promise.id,
            kind=promise.kind,
            primary=promise.id == ledger.primary_promise_id,
            verdict=check.verdict if check else "broken",
            opened=check.opened if check else False,
            progressed=check.progressed if check else False,
            paid=check.paid if check else False,
            evidence=check.evidence if check else "the critic returned no verdict for this promise",
        )

    @staticmethod
    def _validate_note_references(notes: list[RevisionNote], plan: StoryPlan) -> None:
        """Reject critic notes that point outside the canonical plan."""
        chapter_ids = {chapter.id for chapter in plan.chapters}
        event_ids = {event.id for event in plan.events}
        for note in notes:
            if set(note.chapter_ids) - chapter_ids:
                raise ValueError(f"revision note {note.id} references unknown chapters")
            if set(note.event_ids) - event_ids:
                raise ValueError(f"revision note {note.id} references unknown events")

    def _revise_chapters(
        self,
        request: StoryRequest,
        characters: CharactersArtifact,
        plan: StoryPlan,
        presentation: StoryPresentation,
        draft_bodies: list[str],
        review: StoryReview,
        ledger: PromiseLedger | None = None,
    ) -> list[str]:
        """Run Writer for every chapter with one bounded corrective retry."""
        assert self.repository is not None
        writer = WriterAgent(self.provider)
        event_by_id = {event.id: event for event in plan.events}
        revised_bodies: list[str] = []
        revision_results: list[ChapterRevisionResult] = []
        for index, (chapter, draft_body) in enumerate(
            zip(plan.chapters, draft_bodies, strict=True),
            1,
        ):
            percent = 84 + (index - 1) * 12 // len(plan.chapters)
            self._notify(
                percent,
                "revision",
                f"Corrigiendo capítulo {index} de {len(plan.chapters)}",
                index,
                len(plan.chapters),
            )
            events = [
                event_by_id[event_id]
                for event_id in plan.topological_order
                if event_by_id[event_id].chapter_id == chapter.id
            ]
            notes = self._notes_for_chapter(review.notes, chapter, events)
            if notes:
                character_ids = {item for event in events for item in event.character_ids}
                relevant = [item for item in characters.characters if item.id in character_ids]
                accepted, result = self._revise_one_chapter(
                    writer,
                    request,
                    relevant or characters.characters,
                    plan,
                    presentation,
                    chapter,
                    events,
                    notes,
                    draft_body,
                    revised_bodies[-1] if revised_bodies else "",
                    index,
                    self._promise_brief(ledger, chapter.id),
                )
            else:
                accepted, result = (
                    draft_body,
                    self._unrevised_chapter_result(
                        chapter,
                        index,
                        draft_body,
                    ),
                )
            revised_bodies.append(accepted)
            revision_results.append(result)
            self.repository.save_text(f"revisions/chapter-{index:03d}.md", accepted)
            self.repository.save_json(
                "revision_report.json",
                RevisionReport(chapters=revision_results),
            )
        self.repository.complete_stage("revision")
        return revised_bodies

    @staticmethod
    def _notes_for_chapter(
        notes: list[RevisionNote],
        chapter: ChapterPlan,
        events: list[PlotEvent],
    ) -> list[RevisionNote]:
        """Select global notes and notes that target this chapter or its events."""
        event_ids = {event.id for event in events}
        return [
            note
            for note in notes
            # A note is global only when it targets nothing at all. The critic is asked to cite
            # the affected event IDs and to leave chapter_ids empty for global notes, so a note
            # carrying only event_ids is local and must reach just the chapters owning them.
            if (
                not (note.chapter_ids or note.event_ids)
                or chapter.id in note.chapter_ids
                or bool(event_ids.intersection(note.event_ids))
            )
        ]

    @staticmethod
    def _unrevised_chapter_result(
        chapter: ChapterPlan,
        chapter_index: int,
        draft_body: str,
    ) -> ChapterRevisionResult:
        """Record a chapter the critic left untouched, so no Writer call is spent."""
        draft_words = word_count(draft_body)
        return ChapterRevisionResult(
            chapter_id=chapter.id,
            chapter_index=chapter_index,
            note_ids=[],
            draft_words=draft_words,
            attempts=[],
            final_source="draft",
            final_words=draft_words,
        )

    def _revise_one_chapter(
        self,
        writer: WriterAgent,
        request: StoryRequest,
        characters: list[CharacterProfile],
        plan: StoryPlan,
        presentation: StoryPresentation,
        chapter: ChapterPlan,
        events: list[PlotEvent],
        notes: list[RevisionNote],
        draft_body: str,
        previous_revised: str,
        chapter_index: int,
        promise_brief: str = "",
    ) -> tuple[str, ChapterRevisionResult]:
        """Return the first valid Writer candidate or the safe original fallback."""
        assert self.repository is not None
        draft_words = word_count(draft_body)
        attempts: list[ChapterRevisionAttempt] = []
        retry_feedback = ""
        for attempt in range(1, 3):
            prefix = f"writer/chapter-{chapter_index:03d}-attempt-{attempt:03d}"
            try:

                def revise_chapter(feedback_snapshot: str = retry_feedback):
                    """Rewrite the bound chapter with this attempt's feedback."""
                    return writer.run(
                        request,
                        characters,
                        plan,
                        presentation,
                        chapter,
                        events,
                        notes,
                        draft_body,
                        previous_revised,
                        feedback_snapshot,
                        promise_brief,
                    )

                candidate = self._call_agent("writer", revise_chapter).strip()
            except NON_DEGRADABLE_ERRORS:
                raise
            except Exception as exc:
                attempt_result = ChapterRevisionAttempt(
                    attempt=attempt,
                    status="failed",
                    exception_type=type(exc).__name__,
                )
                attempts.append(attempt_result)
                self.repository.save_json(f"{prefix}-validation.json", attempt_result)
                retry_feedback = (
                    "\n\nRETRY CORRECTION:\nThe previous rewrite could not be completed "
                    f"({type(exc).__name__}). Return a complete corrected chapter body."
                )
                continue
            self.repository.save_text(f"{prefix}.md", candidate)
            diagnostic = writer_candidate_issue(candidate, draft_body, notes)
            attempt_result = ChapterRevisionAttempt(
                attempt=attempt,
                status="accepted" if diagnostic is None else "rejected",
                artifact=f"{prefix}.md",
                diagnostic=diagnostic,
            )
            attempts.append(attempt_result)
            self.repository.save_json(f"{prefix}-validation.json", attempt_result)
            if diagnostic is None:
                return candidate, ChapterRevisionResult(
                    chapter_id=chapter.id,
                    chapter_index=chapter_index,
                    note_ids=[note.id for note in notes],
                    draft_words=draft_words,
                    attempts=attempts,
                    final_source="revision",
                    final_words=word_count(candidate),
                )
            retry_feedback = (
                "\n\nRETRY CORRECTION:\nThe previous rewrite was rejected because "
                f"{diagnostic.message}. {diagnostic.retry_instruction} "
                "Return a complete corrected chapter body."
            )
        warning = writer_fallback_warning(chapter_index, draft_words, attempts)
        self.repository.add_warning(warning)
        self._emit("writer_fallback", warning, stage="revision")
        return draft_body, ChapterRevisionResult(
            chapter_id=chapter.id,
            chapter_index=chapter_index,
            note_ids=[note.id for note in notes],
            draft_words=draft_words,
            attempts=attempts,
            final_source="draft",
            final_words=draft_words,
            warning_code="WRITER_REVISION_REJECTED",
        )

    def _finalize(
        self,
        request: StoryRequest,
        plan: StoryPlan,
        story: str,
    ) -> None:
        """Persist observed metrics, evaluation template, metadata, and story."""
        assert self.repository is not None
        self.repository.save_json(
            "story_metrics.json",
            story_metrics(request, plan, story),
        )
        self._publish(story, "Guardando la historia", "Historia terminada")

    def _publish(self, rendered: str, saving_message: str, done_message: str) -> None:
        """Write the final artifact, close the run, and report completion.

        Shared by the narrative story and the theater-script tails, so both formats leave the
        run in the same completed shape: story.md, the evaluation template, optional audio,
        usage, and a completed status.
        """
        assert self.repository is not None
        self._finishing = True
        self._notify(98, "story", saving_message)
        self.repository.save_text("story.md", rendered)
        create_evaluation_template(self.repository.run_dir)
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
        self._emit("agent_called", f"se llamo al agente {name}", stage=self.progress["stage"])
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

    def _notify(
        self,
        percent: int,
        stage: str,
        description: str,
        chapter: int | None = None,
        total: int | None = None,
    ) -> None:
        """Update internal progress and invoke the external progress callback."""
        percent = self._scaled(percent, stage)
        # "rate_limit" is a transient wait notification, not a pipeline checkpoint, so it
        # must not overwrite the real in-progress stage reported by _record_failure.
        if stage != "rate_limit":
            self.progress.update(percent=percent, stage=stage)
        if self.on_progress:
            self.on_progress(ProgressUpdate(percent, stage, description, chapter, total))

    def _scaled(self, percent: int, stage: str) -> int:
        """Compress the pre-performance stages into the first half of a simulated run.

        Writing the script is the whole job of a script run and only the first half of a
        simulated one, so its stages would otherwise report 96% with the performance and the
        narration still to come, and progress would jump backwards at the casting stage.
        """
        if not self._simulated or stage not in PRE_PERFORMANCE_STAGES:
            return percent
        return percent * PRE_PERFORMANCE_CEILING // 100

    def _emit(
        self,
        kind: str,
        message: str,
        *,
        stage: str | None = None,
        attempt: int | None = None,
        artifact: str | None = None,
    ) -> None:
        """Publish a structured pipeline event when a callback is configured."""
        if self.on_event:
            self.on_event(
                PipelineEvent(
                    kind=kind,
                    message=message,
                    stage=stage,
                    attempt=attempt,
                    artifact=artifact,
                )
            )
