"""The prop master: decides which objects are on stage and who opens the play holding them.

Runs once, between casting and the performance, and only when the inventory is on. Like the
casting director it is allowed to read the whole plan, because it is dressing a stage rather
than taking part in what happens on it; unlike the actors, it never sees a turn.

It authors placement, not consequence. What a prop does once the curtain is up is settled by
stage/inventory.py, in code: this agent cannot say that a key opens a door or that a sword
wins a fight, only that the key is in someone's pocket and the sword is on someone's hip.
"""

from ..schemas import CharactersArtifact, StoryPlan, StoryRequest, WorldArtifact
from ..stage.schemas import CastBible, PropListDraft
from .base import Agent, json_text, story_specification_header


class PropMasterAgent(Agent[PropListDraft]):
    """Place every object the performance may handle, before the first scene is played."""

    name = "prop_master"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        plan: StoryPlan,
        bible: CastBible,
        cast_ids: list[str],
        repair_feedback: str = "",
    ) -> PropListDraft:
        """Dress the stage from the frozen plan, the world's objects and the cast's dossiers."""
        relevant = [item for item in characters.characters if item.id in set(cast_ids)]
        return self.provider.generate_structured(
            system_instruction=(
                "You are the Prop Master. The story is planned, staged and cast; you are "
                "dressing the stage before the actors improvise on it. Decide which physical "
                "objects exist and where each one starts: in someone's hands, or lying in a "
                "place. "
                "Every object listed under WORLD must appear in your list, with its own "
                "object_id, because the plan already turns on it. Beyond those, add an object "
                "of a character's own only when it is something they would plainly be carrying "
                "and could use against someone: a weapon they wear, a document they guard, a "
                "tool of their trade. Leave object_id empty for those. Add nothing decorative: "
                "an object nobody would reach for is clutter the actors have to read past. "
                "An object is concealed only when its holder is deliberately keeping it out of "
                "sight and the others would react to seeing it; a concealed object cannot be "
                "seen or taken by anyone else until its holder shows it, so use it for what is "
                "genuinely hidden, never as a default. Only an object with a holder_id can be "
                "concealed. "
                "Place objects where they make the first scene they matter in possible: "
                "something a character must produce early belongs on that character, and "
                "something that has to be found belongs in the place it is found. Give each "
                "object a name that can only mean one thing, because a name is the only handle "
                "an actor will ever have for it. "
                f"Write name and appearance in {request.language}, because the actors read them "
                "directly; everything else is an identifier."
            ),
            prompt=(
                f"{story_specification_header(request)}"
                f"\n\nWORLD:\n{json_text(world)}"
                f"\n\nCHARACTERS:\n{json_text(relevant)}"
                f"\n\nCAST DOSSIERS:\n{json_text(bible.dossiers)}"
                f"\n\nPLAN:\n{json_text(plan)}"
                f"\n\nONLY THESE IDS MAY HOLD AN OBJECT: {', '.join(cast_ids)}"
                f"{repair_feedback}"
            ),
            schema=PropListDraft,
            profile="planning",
        )
