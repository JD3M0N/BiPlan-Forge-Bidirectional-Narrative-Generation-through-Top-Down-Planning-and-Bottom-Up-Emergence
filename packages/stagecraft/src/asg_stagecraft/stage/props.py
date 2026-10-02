"""Deterministic validation of the dressed stage: which objects exist, and where they start.

Same contract and the same language rule as casting.py: every ValueError below is reinjected
verbatim into the prop master's repair prompt, so it stays English ASCII.

Normalize more, reject less. A world object the prop master forgot is placed where the plan
first uses it, something concealed by nobody stops being concealed, and a cast of personal
props longer than a character can play is trimmed. What is rejected is what the arbiter cannot
run on: a holder who is not in the cast, a location that does not exist, two props a character
could not tell apart by name.

The numbers here - how many personal props one character may carry - live in this module and
never travel to a prompt, exactly like the stage's other figures.
"""

from __future__ import annotations

from ..planning.skeleton_match import normalize
from ..schemas import StoryPlan, WorldArtifact
from .schemas import Prop, PropDraft, PropList, PropListDraft

# How many objects of their own one character may open the play holding. Two is what an actor
# can keep in play; the first dressed stage gave one character five and it used none of them.
MAX_PERSONAL_PROPS = 2


def materialize_props(
    draft: PropListDraft,
    *,
    world: WorldArtifact,
    cast_ids: list[str],
    plan: StoryPlan,
) -> PropList:
    """Validate one proposed set of props and mint the trusted version."""
    known_cast = list(dict.fromkeys(cast_ids))
    world_objects = {item.id: item for item in world.objects}
    locations = {item.id for item in world.locations}

    _validate_references(draft.props, known_cast, world_objects, locations)
    props = _minted(draft.props, world_objects)
    # Noted before the corrections are applied, because a silent fix a reader cannot see is the
    # kind of thing that makes a run hard to explain later.
    corrected = [
        f"prop {item.id} was concealed by nobody, so it is in plain sight"
        for item in props
        if item.concealed and not item.holder_id
    ]
    props = _placed(props, world=world, plan=plan, locations=locations)
    trimmed = _trimmed(props, known_cast)
    kept = {item.id for item in trimmed}
    corrected += [
        f"prop {item.id} was more than {item.holder_id} could play, so it was left out"
        for item in props
        if item.id not in kept
    ]
    _validate_distinct_names(trimmed)

    return PropList(
        props=trimmed,
        observations=corrected + _observations(trimmed, world_objects, known_cast),
    )


def fallback_props(world: WorldArtifact, plan: StoryPlan) -> PropList:
    """Place the world's own objects without a model call, when the props stage cannot run.

    Deterministic and offline, like fallback_bible: every object the plan uses lies where it is
    first used, nobody starts out holding anything, and the artifact records that it was derived.
    """
    locations = {item.id for item in world.locations}
    props = _placed(
        [
            Prop(id=item.id, object_id=item.id, name=item.name, appearance=item.description)
            for item in world.objects
        ],
        world=world,
        plan=plan,
        locations=locations,
    )
    return PropList(
        props=props,
        observations=["the props were derived from world.json, not authored"],
        fallback=True,
    )


def props_for_event(props: list[Prop], event_object_ids: list[str]) -> list[Prop]:
    """List the props one plan event turns on, so the director can bring them into a beat."""
    wanted = set(event_object_ids)
    return [item for item in props if item.object_id and item.object_id in wanted]


def _validate_references(
    props: list[PropDraft],
    cast_ids: list[str],
    world_objects: dict,
    locations: set[str],
) -> None:
    """Refuse a prop whose holder, world object or location does not exist."""
    problems: list[str] = []
    strangers = sorted(
        {item.holder_id for item in props if item.holder_id and item.holder_id not in cast_ids}
    )
    if strangers:
        problems.append(
            f"these props are held by characters who are not in the cast ({', '.join(strangers)}); "
            f"only these IDs may hold anything: {', '.join(cast_ids)}"
        )
    unknown = sorted(
        {item.object_id for item in props if item.object_id and item.object_id not in world_objects}
    )
    if unknown:
        allowed = ", ".join(sorted(world_objects)) or "none"
        problems.append(
            f"these props claim world object IDs that do not exist ({', '.join(unknown)}); use "
            f"one of the world's own object IDs or leave object_id empty: {allowed}"
        )
    nowhere = sorted(
        {
            item.location_id
            for item in props
            if not item.holder_id and item.location_id and item.location_id not in locations
        }
    )
    if nowhere:
        problems.append(
            f"these props lie in locations that do not exist ({', '.join(nowhere)}); use one of "
            f"the world's own location IDs: {', '.join(sorted(locations))}"
        )
    if problems:
        raise ValueError("; ".join(problems))


def _minted(props: list[PropDraft], world_objects: dict) -> list[Prop]:
    """Give every prop its identity, keeping a world object's own ID and numbering the rest."""
    minted: list[Prop] = []
    seen_objects: set[str] = set()
    personal = 0
    for item in props:
        if item.object_id:
            if item.object_id in seen_objects:
                continue
            seen_objects.add(item.object_id)
            minted.append(Prop(**item.model_dump(), id=item.object_id))
            continue
        personal += 1
        minted.append(Prop(**item.model_dump(), id=f"prop-{personal}"))
    for object_id, missing in sorted(world_objects.items()):
        if object_id in seen_objects:
            continue
        # A world object the plan cites but the prop master left out is still in the fiction, so
        # the performance gets it rather than being told it does not exist.
        minted.append(
            Prop(
                id=object_id,
                object_id=object_id,
                name=missing.name,
                appearance=missing.description,
            )
        )
    return minted


def _placed(
    props: list[Prop],
    *,
    world: WorldArtifact,
    plan: StoryPlan,
    locations: set[str],
) -> list[Prop]:
    """Give every unheld prop somewhere real to lie, and unconceal what nobody is holding."""
    first_use: dict[str, str] = {}
    for event in plan.events:
        for object_id in event.object_ids:
            if object_id not in first_use and event.location_id in locations:
                first_use[object_id] = event.location_id or ""
    default = world.locations[0].id if world.locations else ""
    placed: list[Prop] = []
    for item in props:
        if item.holder_id:
            placed.append(item.model_copy(update={"location_id": ""}))
            continue
        where = item.location_id or first_use.get(item.object_id or "", "") or default
        placed.append(item.model_copy(update={"location_id": where, "concealed": False}))
    return placed


def _trimmed(props: list[Prop], cast_ids: list[str]) -> list[Prop]:
    """Keep every character's personal props down to what they could actually play.

    A world object is never trimmed: the plan may depend on it. What is dropped is the extra
    invented prop, and its holder keeps the first ones proposed.
    """
    carried: dict[str, int] = {}
    kept: list[Prop] = []
    for item in props:
        if item.holder_id and not item.object_id:
            carried[item.holder_id] = carried.get(item.holder_id, 0) + 1
            if carried[item.holder_id] > MAX_PERSONAL_PROPS:
                continue
        kept.append(item)
    return kept


def _validate_distinct_names(props: list[Prop]) -> None:
    """Refuse two props an actor could not tell apart, since a name is the only handle it gets."""
    seen: dict[str, str] = {}
    clashes: list[str] = []
    for item in props:
        key = normalize(item.name)
        if key in seen:
            clashes.append(f"{seen[key]} and {item.id}")
        else:
            seen[key] = item.id
    if clashes:
        raise ValueError(
            f"these props share a name ({'; '.join(clashes)}); an actor only ever sees names, so "
            "give every object a name that can only mean one thing"
        )


def _observations(props: list[Prop], world_objects: dict, cast_ids: list[str]) -> list[str]:
    """Report non-blocking findings a usable set of props can still carry."""
    observations: list[str] = []
    if not props:
        observations.append("the stage was dressed with no objects at all")
    unheld = [item.id for item in props if not item.holder_id]
    if props and len(unheld) == len(props):
        observations.append("nobody opens the play holding anything")
    for character_id in cast_ids:
        if not any(item.holder_id == character_id for item in props):
            observations.append(f"{character_id} opens the play empty-handed")
    missing = sorted(set(world_objects) - {item.object_id for item in props})
    if missing:
        observations.append(f"world objects absent from the stage: {', '.join(missing)}")
    return observations
