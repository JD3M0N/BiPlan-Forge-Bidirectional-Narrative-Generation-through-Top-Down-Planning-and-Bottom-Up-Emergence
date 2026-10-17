"""The scene planner: turns every event of the frozen plan into the scenes the Drafter writes.

Runs once per story, after the plan is frozen (the scene_cards option, 7.17). It decides how the
plan is staged, never what happens: planning/scene_cards.py rejects a card for an event the plan
does not have and an event left without one.
"""

from ..schemas import CharactersArtifact, SceneCardsDraft, StoryPlan, StoryRequest, WorldArtifact
from .base import Agent, json_text, story_specification_header


class SceneCardAgent(Agent[SceneCardsDraft]):
    """Draw one or two scene cards per plan event, in plan order."""

    name = "scene_planner"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        feedback: str = "",
    ) -> SceneCardsDraft:
        """Return the scene cards of the whole story."""
        events = {event.id: event for event in plan.events}
        ordered = [events[event_id] for event_id in plan.topological_order]
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Scene Planner. Turn every event of the frozen plan into one scene, "
                "or two when it needs an action and then a reaction, for the Drafter to write, "
                "in plan order. Ids stay exactly as given; write every other field in "
                f"{request.language}. A scene puts named characters in one place. Each of them "
                "wants something right now; the first attempt fails on an obstacle; and by the "
                "end something has turned - a decision, a discovery or a reversal the reader "
                "sees. Give it one concrete sensory detail of the place, drawn from the WORLD; "
                "one thing the reader must understand without anyone saying it; and an ending on "
                "an image or a line, never on a summary of how things turned out. The scenes of "
                "the last event make its cost visible: what someone loses or gives up. Add no "
                "event, character or outcome the plan does not have."
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nPLANNED EVENTS IN ORDER:\n{json_text(ordered)}"
                f"{feedback}"
            ),
            schema=SceneCardsDraft,
            profile="planning",
        )
