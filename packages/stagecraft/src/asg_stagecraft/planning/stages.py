"""The planning stages: blueprint, world, cast, plan and promise ledger (7.20, ING-3).

Split from pipeline.py, which mixes this in like script/stages.py and stage/stages.py; it
calls the helpers pipeline.py defines (self.repository, self._call_agent, self._notify).
"""

from __future__ import annotations

from collections.abc import Callable

from ..agents import (
    CharacterDesignerAgent,
    PlanCriticAgent,
    PlotPlannerAgent,
    PromiseLedgerAgent,
    StoryArchitectAgent,
    WorldBuilderAgent,
)
from ..brief import (
    authored_cast_block,
    authored_plot_block,
    cast_repair_feedback,
    missing_cast,
)
from ..runtime.errors import (
    NON_DEGRADABLE_ERRORS,
    PlotValidationError,
    StructuredResponseError,
)
from ..schemas import (
    CharactersArtifact,
    NarrativeBlueprint,
    PromiseLedger,
    PromiseLedgerDraft,
    StoryPlan,
    StoryPlanDraft,
    StoryRequest,
    WorldArtifact,
)
from .catalog_types import GuidanceStrategy
from .graph import (
    materialize_plan,
    validate_profile_structure,
    validate_story_plan,
)
from .guidance_composition import compose_patterns
from .guidance_models import CompositionArtifact, CompositionFailure
from .guidance_retrieval import retrieve_patterns
from .names import choose_names
from .profiles import NarrativeProfile
from .promise_brief import event_index, rendered_ledger
from .promises import materialize_ledger
from .repair import repair_guidance

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

# The world has no repair prompt of its own: the provider already resends the validation errors,
# so a second stage attempt is a fresh draw. 7.10 lost a run to one bad location id here.
WORLD_ATTEMPTS = 2


class PlanningStagesMixin:
    """Build everything a story is planned from, up to the frozen plan and its ledger."""

    def _build_blueprint(
        self, request: StoryRequest
    ) -> NarrativeBlueprint | CompositionArtifact | None:
        """Propose optional structural inspiration without ever failing the run."""
        assert self.repository is not None
        if not self.narrative_guidance:
            return None
        self._notify(6, "architecture", "Eligiendo el esqueleto narrativo")

        def build_blueprint():
            """Read the bound request against the plot skeleton catalog."""
            if self.options.guidance_strategy == GuidanceStrategy.COMPOSITIONAL_V2:
                retrieval = retrieve_patterns(request, self.provider)
                self.repository.save_json("narrative_retrieval.json", retrieval)
                if retrieval.degraded:
                    self.repository.add_warning(
                        "La recuperación narrativa falló; "
                        "la historia continúa sin guía de patrones; "
                        "ver narrative_retrieval.json."
                    )
                composed = compose_patterns(request, retrieval, self.provider)
                if isinstance(composed, CompositionFailure):
                    self.repository.save_json("narrative_composition_error.json", composed)
                    raise ValueError("narrative composition failed after one repair")
                return composed
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
        if isinstance(blueprint, CompositionArtifact) and blueprint.abstained:
            return None
        return blueprint

    def _build_world(self, request: StoryRequest) -> WorldArtifact:
        """Generate and persist the story world artifact."""
        assert self.repository is not None
        self._notify(12, "world", "Construyendo el mundo")

        def build_world():
            """Generate the world for the bound story request."""
            return WorldBuilderAgent(self.provider).run(request)

        for attempt in range(1, WORLD_ATTEMPTS + 1):
            try:
                world = self._call_agent("world", build_world)
                break
            except StructuredResponseError as exc:
                self.repository.save_data(
                    f"world_attempt-{attempt:03d}-validation.json", exc.details
                )
                if attempt == WORLD_ATTEMPTS:
                    raise
        self.repository.save_json("world.json", world)
        self.repository.complete_stage("world")
        return world

    def _build_characters(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        blueprint: NarrativeBlueprint | CompositionArtifact | None = None,
    ) -> CharactersArtifact:
        """Generate and persist the story character artifact."""
        assert self.repository is not None
        self._notify(25, "characters", "Diseñando los personajes")

        def build_characters(feedback: str = ""):
            """Generate characters for the bound request and world."""
            return CharacterDesignerAgent(self.provider).run(
                request, world, blueprint, feedback, authored_cast=authored_cast_block(self.brief)
            )

        characters = self._call_agent("characters", build_characters)
        if self.brief is not None and self.brief.cast:
            characters = self._keep_declared_cast(characters, build_characters)
        fixed = [member.name for member in self.brief.cast] if self.brief is not None else []
        characters, choices = choose_names(characters, fixed, request.original_prompt)
        if choices:
            self.repository.save_data("name_choices.json", {"choices": choices})
        characters = self._localized_characters(request, characters)
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
        blueprint: NarrativeBlueprint | CompositionArtifact | None = None,
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
                    authored_plot=authored_plot_block(self.brief),
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
        blueprint: NarrativeBlueprint | CompositionArtifact | None = None,
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
                    authored_plot=authored_plot_block(self.brief),
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
                    authored_plot=authored_plot_block(self.brief),
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
