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
        *,
        authored_cast: str = "",
        first_scenes: str = "",
    ) -> CastBibleDraft:
        """Derive the cast bible from the frozen plan and the characters already designed.

        authored_cast is the cast block of a structured brief: ages, trades and secrets the
        dossiers must keep. Empty for a free prompt.
        """
        relevant = [item for item in characters.characters if item.id in set(cast_ids)]
        scenes_block = f"\n\nFIRST SCENES:\n{first_scenes}" if first_scenes else ""
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
                "Give each one a public_face: what anyone who sees them can tell at a glance, "
                "including apparent gender and age, so the others address them correctly. "
                "Then set their knowledge boundary. initial_knowledge is everything this "
                "character already knows when the story opens; anything you leave out they "
                "must learn on stage. A character who belongs to a place of the WORLD knows it "
                "as anyone born there does: put in their initial_knowledge, in concrete terms, "
                "the customs, money, laws, institutions and told history of that place they "
                "live by, so they can use or explain them on stage; an outsider knows none of "
                "it. This is ordinary knowledge, never a gate fact or a secret. "
                "initial_knowledge pictures the moment before each character's first scene, "
                "listed under FIRST SCENES: never the outcome of an event at or after it, not "
                "even the situation the play will put them in later - where they will end up, "
                "how others will treat them. For every fact add its source to "
                "knowledge_sources, in the same order: 'world', 'backstory', or the id of the "
                "earlier plan event it comes from. A character who keeps a secret also gets a "
                "cover_story: the version of events they tell instead, as they would say it. "
                "Use knowledge_gates for the facts some characters hold and "
                "others do not - a secret, a lie, a piece of evidence. For each gate keep two "
                "things apart that are easy to confuse: known_by lists who ALREADY knows the "
                "fact before the first scene, while revealed_by and how say who brings it out on "
                "stage and by what means. The culprit knows what they did; the detective does "
                "not know the answer and works it out, so the detective is the revealed_by of a "
                "deduction and is never in its known_by, and never has it in initial_knowledge. "
                "Every deduction must list premise_gate_ids revealed earlier, or "
                "initial_premises copied "
                "exactly from its investigator initial_knowledge. Never include "
                "its conclusion as a premise. "
                "Whoever confesses must already know. Whatever the plan has the cast discover "
                "in a later event - a measurement, a deduction, a truth they piece together - is "
                "a knowledge gate revealed on stage: never in the initial_knowledge or the secret "
                "of whoever will discover it; only someone hiding it may know it already. "
                "A reveal must tell someone present "
                "something new. Asymmetry is the point: a cast that all know the same things has "
                "no scenes to play. Antagonists get the same care as protagonists; write what "
                "they want and why it is worth wanting, never a label for how bad they are. "
                "Use only the character IDs listed. Write public_face, initial_knowledge, "
                f"cover_story, initial_emotion, initial_goal and every gate fact in "
                f"{request.language}, "
                "because they reach the actors directly; write other dossier fields in English."
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nCHARACTERS:\n{json_text(relevant)}"
                f"{authored_cast}"
                f"\n\nRELATIONSHIPS:\n{json_text(characters.relationships)}"
                f"\n\nPLAN:\n{json_text(plan)}"
                f"{scenes_block}"
                f"\n\nSTAGING SUMMARY:\n{staging}"
                f"\n\nWRITE ONE DOSSIER FOR EACH OF THESE IDS: {', '.join(cast_ids)}"
                f"{repair_feedback}"
            ),
            schema=CastBibleDraft,
            profile="planning",
        )
