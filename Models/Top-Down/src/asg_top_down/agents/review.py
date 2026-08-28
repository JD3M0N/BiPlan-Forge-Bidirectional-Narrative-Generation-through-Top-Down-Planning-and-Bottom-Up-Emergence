"""Single-pass review and editing."""

from .base import Agent, json_text
from ..schemas import StoryPlan, StoryRequest, StoryReview


class StoryCriticAgent(Agent[StoryReview]):
    name = "story_critic"

    def run(self, request: StoryRequest, plan: StoryPlan, draft: str) -> StoryReview:
        return self.provider.generate_structured(
            system_instruction=(
                "Review the complete draft for causal continuity, character motivation, clarity, pacing, "
                "language, and compliance with every explicit user constraint. Give concrete revision "
                "instructions. Do not score the story and do not invent requirements."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nPLAN:\n{json_text(plan)}"
                f"\n\nDRAFT:\n{draft}"
            ),
            schema=StoryReview,
        )


class StoryEditorAgent(Agent[str]):
    name = "story_editor"

    def run(
        self, request: StoryRequest, plan: StoryPlan, draft: str, review: StoryReview,
    ) -> str:
        return self.provider.generate_text(
            system_instruction=(
                f"Edit the complete story once in {request.language}. Apply the concrete review, preserve "
                "the planned events and Markdown chapter headings, and return only the final story. Do not "
                "mention the review or the generation process."
            ),
            prompt=(
                f"STORY SPECIFICATION:\n{json_text(request.agent_spec())}"
                f"\n\nPLAN:\n{json_text(plan)}"
                f"\n\nREVIEW:\n{json_text(review)}"
                f"\n\nDRAFT:\n{draft}"
            ),
        )
