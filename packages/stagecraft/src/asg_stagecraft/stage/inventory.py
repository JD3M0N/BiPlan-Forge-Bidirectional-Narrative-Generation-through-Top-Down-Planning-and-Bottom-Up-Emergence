"""The arbiter of physical objects: who holds what, and who saw it change hands.

The model proposes, the code decides. An actor writes a verb and the name of an object, and
nothing else about the object is taken on trust: whether it exists, whether that character is
holding it, whether it is within reach, and who perceives the move are all answered here, from
state this module owns. Concordia's inventory asks a language model after the fact what changed,
which cannot be replayed; this is deterministic, like stage/memory.py, so the same performance
scores the same on any machine.

Why it earns its place: in the first simulated runs of the corpus a seal surfaced in one
character's hands in chapter two and reappeared in another's tunic in chapter three, with no
hand-over ever performed. Nothing contradicted either turn, because nothing was tracking the
object. Here a turn that reaches for what it does not hold is rejected with an English message
the actor is handed back, exactly like a repeated line.

Perception is the second half, and the reason the inventory belongs in this package rather than
in a prompt: an object moves in front of whoever is there to see it, so the memory each actor
keeps of who has what diverges, and a point of view can only narrate the transfers its narrator
witnessed. A concealed object is the extreme case - only its holder ever knows it is there.
"""

from __future__ import annotations

from collections.abc import Callable

from ..formats import ActorMemory
from ..planning.skeleton_match import normalize
from .perception import ordered_witnesses
from .render import prop_line
from .schemas import ItemAction, ItemActionDraft, Prop, TurnVisibility
from .validation import TurnIssue

# A word of an object's name shorter than this says too little to pick one prop out of a scene,
# the same threshold the addressee resolution uses for a character's name.
_MIN_ITEM_WORD = 3

# The verbs whose object must already be in the actor's own hands.
_NEEDS_HELD = frozenset({"use", "give", "drop", "hide", "show"})


class StageInventory:
    """Track where every prop is, and judge each object move an actor proposes.

    The opening truth comes from props.json; from the first turn on, this object owns it. Where
    a prop lies is kept per location, so something dropped in one scene is still there when a
    later scene plays in the same place.
    """

    def __init__(
        self,
        props: list[Prop],
        *,
        actor_memory: ActorMemory = ActorMemory.OWN,
        on_item: Callable[[dict], None] | None = None,
    ) -> None:
        """Take the dressed stage as the opening truth and start tracking it."""
        self.actor_memory = actor_memory
        self.on_item = on_item
        self._props = {item.id: item for item in props}
        self._holder = {item.id: item.holder_id for item in props}
        self._location = {item.id: "" if item.holder_id else item.location_id for item in props}
        self._concealed = {item.id: item.concealed and bool(item.holder_id) for item in props}
        # Every prop that was ever handled, so the metrics can say what share of the dressed
        # stage the performance actually used.
        self.handled: set[str] = set()

    # -- what an actor can see -----------------------------------------------------------

    def held_by(self, character_id: str) -> list[Prop]:
        """List what one character is carrying, concealed items included, in a stable order."""
        return [
            self._props[item]
            for item in sorted(self._props)
            if self._holder.get(item) == character_id
        ]

    def in_reach(self, character_id: str, on_stage: list[str], location_id: str) -> list[Prop]:
        """List what one character can see without holding it: on the floor, or on someone else.

        A concealed object is absent from this list for everyone but its holder, which is the
        whole point of concealing it.
        """
        visible = []
        for item in sorted(self._props):
            holder = self._holder.get(item, "")
            if holder == character_id:
                continue
            if holder:
                if holder in on_stage and not self._concealed.get(item):
                    visible.append(self._props[item])
            elif location_id and self._location.get(item) == location_id:
                visible.append(self._props[item])
        return visible

    def director_view(
        self, on_stage: list[str], location_id: str, names: dict[str, str]
    ) -> list[str]:
        """Describe who is holding what right now, for the director alone.

        The director sees concealed objects, unlike every actor but their holder: it is the one
        agent that can point a character at something it is carrying and has stopped playing.
        """
        lines = []
        for character_id in on_stage:
            held = self.held_by(character_id)
            if held:
                carried = ", ".join(prop_line(item) for item in held)
                lines.append(f"{names.get(character_id, character_id)} lleva: {carried}")
        lying = [
            self._props[item]
            for item in sorted(self._props)
            if not self._holder.get(item) and self._location.get(item) == location_id
        ]
        if lying:
            lines.append("A la vista en el lugar: " + ", ".join(item.name for item in lying))
        return lines

    # -- judging one move ----------------------------------------------------------------

    def resolve(
        self,
        draft: ItemActionDraft,
        *,
        actor_id: str,
        on_stage: list[str],
        location_id: str,
        names: dict[str, str],
        visibility: TurnVisibility,
        addressed_to: list[str],
        whole_cast: list[str],
    ) -> ItemAction | None:
        """Accept one proposed object move, or raise a TurnIssue saying in English what to fix.

        Returns None for a turn that handles no object, which is most turns.
        """
        if draft.verb == "none" or not draft.item.strip():
            return None
        prop = self._find(draft.item, actor_id, on_stage, location_id)
        if prop is None:
            raise TurnIssue(
                "UNKNOWN_ITEM",
                "there is no such object within your reach; handle only what is listed as "
                "yours or as something you can see, or take no object this turn",
            )
        holder = self._holder.get(prop.id, "")
        if draft.verb in _NEEDS_HELD and holder != actor_id:
            raise TurnIssue(
                "ITEM_NOT_HELD",
                "you are not holding that object, so you cannot do this with it; take it "
                "first, or do something else",
            )
        if draft.verb == "take":
            if holder == actor_id:
                raise TurnIssue(
                    "ITEM_OUT_OF_REACH", "you are already holding that object; use it instead"
                )
            if holder and holder not in on_stage:
                raise TurnIssue(
                    "ITEM_OUT_OF_REACH",
                    "whoever holds that object is not here, so you cannot take it now",
                )
            if not holder and self._location.get(prop.id) != location_id:
                raise TurnIssue(
                    "ITEM_OUT_OF_REACH", "that object is not here, so you cannot pick it up now"
                )
        target_id = self._target(draft, prop, actor_id, on_stage, names)
        return ItemAction(
            verb=draft.verb,
            item_id=prop.id,
            item_name=prop.name,
            target_id=target_id,
            from_id=holder if draft.verb in {"give", "take"} else "",
            witnesses=self._witnesses(
                verb=draft.verb,
                actor_id=actor_id,
                target_id=target_id,
                from_id=holder,
                on_stage=on_stage,
                whole_cast=whole_cast,
                visibility=visibility,
                addressed_to=addressed_to,
            ),
        )

    def apply(self, action: ItemAction, *, actor_id: str, location_id: str) -> None:
        """Move the object the way an accepted action says, and record that it was handled."""
        self.handled.add(action.item_id)
        if action.verb == "give" and action.target_id:
            self._holder[action.item_id] = action.target_id
            self._location[action.item_id] = ""
            self._concealed[action.item_id] = False
        elif action.verb == "take":
            self._holder[action.item_id] = actor_id
            self._location[action.item_id] = ""
            self._concealed[action.item_id] = False
        elif action.verb == "drop":
            self._holder[action.item_id] = ""
            self._location[action.item_id] = location_id
            self._concealed[action.item_id] = False
        elif action.verb == "hide":
            self._concealed[action.item_id] = True
        elif action.verb in {"show", "use"}:
            # Using a concealed object in front of people is showing it, whatever it is for.
            self._concealed[action.item_id] = False
        if self.on_item:
            self.on_item(
                {**action.model_dump(mode="json"), "holder_id": self.holder(action.item_id)}
            )

    # -- reading the truth ---------------------------------------------------------------

    def holder(self, item_id: str) -> str:
        """Name whoever is holding one prop, or nothing when it lies somewhere."""
        return self._holder.get(item_id, "")

    def snapshot(self) -> list[Prop]:
        """Return every prop as it stands now, in a stable order."""
        return [
            self._props[item].model_copy(
                update={
                    "holder_id": self._holder.get(item, ""),
                    "location_id": self._location.get(item, ""),
                    "concealed": self._concealed.get(item, False),
                }
            )
            for item in sorted(self._props)
        ]

    # -- internals -----------------------------------------------------------------------

    def _find(
        self, written: str, actor_id: str, on_stage: list[str], location_id: str
    ) -> Prop | None:
        """Map what an actor wrote onto one prop it can reach, or nothing when it is ambiguous.

        Resolved like an addressee: by exact name, accent-folded, or by a single word of the
        name when that word can only mean one of the objects in front of them. IDs are never
        offered to an actor, so they are not accepted here either.
        """
        candidates = [*self.held_by(actor_id), *self.in_reach(actor_id, on_stage, location_id)]
        keys: dict[str, set[str]] = {}
        for prop in candidates:
            name = normalize(prop.name)
            handles = {name}
            handles.update(word for word in name.split() if len(word) >= _MIN_ITEM_WORD)
            for key in handles:
                if key:
                    keys.setdefault(key, set()).add(prop.id)
        matches = keys.get(normalize(written), set())
        if len(matches) != 1:
            return None
        (item_id,) = matches
        return self._props[item_id]

    def _target(
        self,
        draft: ItemActionDraft,
        prop: Prop,
        actor_id: str,
        on_stage: list[str],
        names: dict[str, str],
    ) -> str:
        """Resolve who a move is aimed at, rejecting a hand-over that has nobody to receive it."""
        written = draft.target.strip()
        resolved = ""
        if written:
            keys: dict[str, set[str]] = {}
            for character_id in on_stage:
                name = normalize(names.get(character_id, ""))
                handles = {name}
                handles.update(word for word in name.split() if len(word) >= _MIN_ITEM_WORD)
                for key in handles:
                    if key:
                        keys.setdefault(key, set()).add(character_id)
            matches = keys.get(normalize(written), set())
            if len(matches) == 1:
                (resolved,) = matches
        if draft.verb == "give" and (not resolved or resolved == actor_id):
            raise TurnIssue(
                "INVALID_ITEM_TARGET",
                "name the one person present who receives the object, as they are listed on "
                "stage, or keep it",
            )
        if draft.verb == "take":
            # A taker may name whoever they take it from, or just reach for it; either way the
            # truth is who was holding it, so a wrong or missing name costs nothing.
            return self._holder.get(prop.id, "")
        return "" if resolved == actor_id else resolved

    def _witnesses(
        self,
        *,
        verb: str,
        actor_id: str,
        target_id: str,
        from_id: str,
        on_stage: list[str],
        whole_cast: list[str],
        visibility: TurnVisibility,
        addressed_to: list[str],
    ) -> list[str]:
        """List who perceives one object move.

        Concealing is private by definition: nobody sees a thing go out of sight, so the holder
        is the only witness however the turn was spoken. Everything else is perceived like the
        turn that carried it, plus whoever the object left or reached - a hand-over whispered
        between two characters is a secret the rest of the stage does not get.
        """
        if verb == "hide":
            return [actor_id]
        parties = [item for item in (target_id, from_id) if item and item != actor_id]
        if visibility == "whisper":
            addressed = [item for item in on_stage if item in set(addressed_to)]
            return ordered_witnesses(actor_id, [*addressed, *parties], [*on_stage, *parties])
        audience = whole_cast if self.actor_memory is ActorMemory.SHARED else on_stage
        return ordered_witnesses(actor_id, [*audience, *parties], [*audience, *parties])
