"""The actor: one character, one turn at a time, acting on what it alone remembers.

Every call is made with a system instruction built from this character's dossier and a user
block built from this character's memory. Nothing else reaches it - no plan, no event IDs, no
later scene, no line from the script. That is the whole point: what the character does next has
to come from what the character knows, or the performance is a recitation and the run proves
nothing.

The three-channel turn (thought, action, speech) is what makes the asymmetry usable. A thought
is never perceived by anyone else, so a character can lie on stage while the log records that it
lied, and the narrator can later dramatize the gap.
"""

from ..stage.schemas import ActorTurnDraft, ReflectionDraft
from .base import Agent


class ActorAgent(Agent[ActorTurnDraft]):
    """Play one character's next move, and afterwards reflect on the scene in its own voice."""

    name = "actor"

    def run(
        self,
        system_instruction: str,
        context: str,
        retry_feedback: str = "",
    ) -> ActorTurnDraft:
        """Take one turn in the current scene from the bound character's point of view."""
        return self.provider.generate_structured(
            system_instruction=system_instruction,
            prompt=(
                f"{context}\n\n"
                "Te toca. Haz un solo movimiento: di algo, haz algo, o las dos cosas. "
                "Escribe solo lo que dices y lo que haces, sin tu nombre delante y sin comillas."
                f"{retry_feedback}"
            ),
            schema=ActorTurnDraft,
            profile="prose",
        )

    def reflect(
        self,
        system_instruction: str,
        scene_log: str,
        language: str,
    ) -> ReflectionDraft:
        """Close one scene from inside the character: what it now believes and how it stands.

        Written in the first person on purpose. A memory recorded as "Ana learned that..." reads
        back to the actor as a report about someone else; one recorded as "I learned that..."
        reads back as experience, and the next turn plays from it.
        """
        return self.provider.generate_structured(
            system_instruction=system_instruction,
            prompt=(
                "La escena ha terminado. Mirala hacia atras desde dentro de ti.\n\n"
                f"{scene_log}\n\n"
                f"Escribe en primera persona y en {language}: que has hecho y que te ha pasado, "
                "que crees ahora que antes no creias, y como te has quedado con cada uno de los "
                "que estaban ahi. Cuenta solo lo que tu has vivido o te han dicho en esta escena."
            ),
            schema=ReflectionDraft,
            profile="planning",
        )
