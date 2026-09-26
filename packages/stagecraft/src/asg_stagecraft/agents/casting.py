"""The casting director: turns a planned cast into actors who can be played.

This agent is the one place in the pipeline that is allowed to read the whole plan *and* write
about the characters, because it is preparing a performance rather than taking part in one.
What it produces never reaches the narrative or script formats: characters.json is untouched, so
a corpus generated before this stage existed stays comparable with one generated after.
"""

from ..schemas import CharactersArtifact, StoryPlan, StoryRequest, WorldArtifact
from ..stage.schemas import CastBibleDraft
from .base import Agent, json_text, story_specification_header


class CastingDirectorAgent(Agent[CastBibleDraft]):
    """Write one playable dossier per cast member, plus who knows what when the curtain rises."""

    name = "casting_director"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        cast_ids: list[str],
        staging: str,
        repair_feedback: str = "",
    ) -> CastBibleDraft:
        """Derive the cast bible from the frozen plan and the characters already designed."""
        relevant = [item for item in characters.characters if item.id in set(cast_ids)]
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Casting Director. The story is already planned and staged; you are "
                "preparing the actors who will improvise it. For every character listed, write a "
                "dossier an actor could play from tonight. Write behavior, not portraiture: "
                "'always answers a question with a question' is playable, 'is evasive' is not. "
                "Give each one a want they pursue on stage, the need underneath it, the wound "
                "that explains them, the line they will not cross, and the tactics they switch "
                "between when blocked. Give them a voice concrete enough that another actor "
                "could imitate it. "
                "Then set their knowledge boundary: initial_knowledge is everything this "
                "character already knows when the story opens, and anything you leave out they "
                "must learn on stage. Use knowledge_gates for the facts that some characters "
                "know and others do not — a secret, a lie, a piece of evidence — naming who "
                "holds each one and, when the plan reveals it, the event where it comes out. "
                "Asymmetry is the point: a cast that all know the same things has no scenes to "
                "play. Antagonists get the same care as protagonists; write what they want and "
                "why it is worth wanting, never a label for how bad they are. "
                "Use only the character IDs listed. Return every field in English."
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nCHARACTERS:\n{json_text(relevant)}"
                f"\n\nRELATIONSHIPS:\n{json_text(characters.relationships)}"
                f"\n\nPLAN:\n{json_text(plan)}"
                f"\n\nSTAGING SUMMARY:\n{staging}"
                f"\n\nWRITE ONE DOSSIER FOR EACH OF THESE IDS: {', '.join(cast_ids)}"
                f"{repair_feedback}"
            ),
            schema=CastBibleDraft,
            profile="planning",
        )
