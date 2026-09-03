"""Plan and complete-draft criticism."""

from ..profiles import profile_guidance
from ..schemas import (
    CharactersArtifact,
    PlanReview,
    StoryPlan,
    StoryPresentation,
    StoryRequest,
    StoryReview,
    WorldArtifact,
)
from .base import Agent, json_text


class PlanCriticAgent(Agent[PlanReview]):
    """Critique one structurally valid plan before prose begins."""

    name = "plan_critic"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
    ) -> PlanReview:
        """Return actionable English notes or approve the plan."""
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Plan Critic. Review a structurally valid story plan for fidelity to explicit "
                "constraints, causal coherence, originality, agency, character motivation, escalation, "
                "world continuity, pacing, setup/payoff, and qualitative narrative-profile compliance. "
                "Do not infer profile compliance from prose length or event count alone: verify that every "
                "event is a distinct state change, Developed plans sustain their secondary arc, and "
                "Expansive plans sustain meaningful subplots and interacting arcs across their branch and join. "
                "Flexible creative directions may be adapted "
                "but must not override constraints. Return every field in English. Do not score the plan. "
                "If no material change is needed, approve it with no notes. Otherwise reject it and provide "
                "specific notes with unique lowercase IDs, evidence, instructions, and valid chapter/event "
                "IDs. Do not invent user requirements."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nNARRATIVE PROFILE CONTRACT:\n{profile_guidance(request.narrative_profile)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nVALIDATED PLAN:\n{json_text(plan)}"
            ),
            schema=PlanReview,
        )


class DramaCriticAgent(Agent[StoryReview]):
    """Read the complete draft and create coordinated revision notes."""

    name = "drama_critic"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        presentation: StoryPresentation,
        draft: str,
    ) -> StoryReview:
        """Run the global-to-local drama criticism workflow."""
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Drama Critic. Read the complete draft and return coordinated revision notes "
                "in English; never rewrite the story. Check every explicit constraint plus causal and world "
                "continuity, character motivation and agency, dramatic structure, pacing and tension, "
                "setup/payoff, qualitative narrative-profile compliance, originality, voice, "
                "requested-language consistency, and stray anglicisms. "
                "For Developed and Expansive profiles, examine every planned event of each chapter "
                "individually: did it receive its own visible action, reaction, and consequence, or was it "
                "absorbed into a neighboring event's beat or reduced to a passing mention? A correct event "
                "or chapter count does not by itself satisfy the profile. When an event lacks its own scene, "
                "raise a pacing-category note with major or critical priority, cite the affected event IDs as "
                "evidence, and give a concrete dramatization instruction (for example, give event_X its own "
                "reaction beat before continuing to event_Y) — never a word-count or length instruction. "
                "Use empty chapter_ids for global notes and exact canonical chapter IDs for local notes. "
                "Each note needs a unique lowercase ID, priority, category, evidence, and a concrete "
                "instruction the Writer can apply. Do not score the story or invent user requirements."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nNARRATIVE PROFILE CONTRACT:\n{profile_guidance(request.narrative_profile)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nPLAN:\n{json_text(plan)}"
                f"\n\nLOCALIZED PRESENTATION:\n{json_text(presentation)}"
                f"\n\nDRAFT:\n{draft}"
            ),
            schema=StoryReview,
        )
