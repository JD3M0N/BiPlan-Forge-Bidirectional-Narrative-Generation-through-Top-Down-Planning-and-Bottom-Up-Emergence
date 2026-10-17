"""Deterministic validation of one cast bible against the frozen plan and cast.

Same contract as script/validation.py, and the same language rule: every ValueError below is
reinjected verbatim into the casting director's repair prompt, so it stays English ASCII.

Normalize more, reject less. A relationship pointing at a character who does not exist, a secret
kept from nobody, a character listed twice: each has exactly one sensible correction, so it is
corrected rather than bounced. What is rejected is what the performance cannot run without - a
missing dossier, an unplayable want, a gate anchored to an event the plan never contains.

The fallback matters as much as the validation. Losing the bible must not lose the run, so
``fallback_bible`` derives a thin but usable dossier straight from characters.json: the
performance then runs on less, and the artifact says so.
"""

from __future__ import annotations

from ..schemas import CharacterProfile, CharactersArtifact, StoryPlan
from .schemas import ActorDossier, ActorRelationship, CastBible, CastBibleDraft, KnowledgeGate
from .validation import similarity

# How closely a character's starting knowledge may resemble a fact they are meant to work out
# on stage before it counts as having been handed the answer. Lexical, like the rest of the
# stage's deterministic checks.
KNOWLEDGE_OVERLAP = 0.4
# A holder cannot deduce or discover what they already hold.
LEARNED_ON_STAGE = frozenset({"deduction", "discovery"})
# The verb each way of learning on stage takes in a correction sent back to the model.
_LEARNS = {"deduction": "works out", "discovery": "discovers"}


def materialize_bible(
    draft: CastBibleDraft,
    *,
    cast_ids: list[str],
    characters: CharactersArtifact,
    plan: StoryPlan,
    drop_invalid_gates: bool = False,
    future_events: dict[str, set[str]] | None = None,
    on_stage: dict[str, set[str]] | None = None,
) -> CastBible:
    """Validate one proposed cast bible and mint the trusted version.

    With drop_invalid_gates, a gate that breaks a rule is left out instead of rejecting the
    bible: the last casting attempt uses it, so that one bad gate no longer costs every
    dossier (7.14). The rules themselves are the same; a dropped gate is never weakened.
    """
    known_characters = {item.id for item in characters.characters}
    known_events = {event.id for event in plan.events}
    required = list(dict.fromkeys(cast_ids))

    dossiers = _deduplicate(draft.dossiers, known_characters)
    _validate_coverage(dossiers, required)
    _validate_playable(dossiers)
    dossiers = [_normalize_dossier(item, known_characters) for item in dossiers]
    observations: list[str] = []
    if future_events is not None:
        dossiers = [_without_future_facts(item, future_events, observations) for item in dossiers]

    gates = _normalize_gates(draft.knowledge_gates, known_characters)
    if drop_invalid_gates:
        kept: list[KnowledgeGate] = []
        for gate in gates:
            issue = _gate_issue(gate, gates, dossiers, plan, known_events) or _revealer_issue(
                gate, on_stage
            )
            if issue:
                observations.append(f"gate {gate.id} dropped: {issue}")
            else:
                kept.append(gate)
        dropped = {gate.id for gate in gates} - {gate.id for gate in kept}
        # A premise that was dropped takes its deductions with it.
        gates = [gate for gate in kept if not dropped & set(gate.premise_gate_ids)]
    _validate_gates(gates, dossiers, plan, known_events)
    for gate in gates:
        issue = _revealer_issue(gate, on_stage)
        if issue:
            raise ValueError(issue)

    return CastBible(
        dossiers=dossiers,
        knowledge_gates=gates,
        observations=observations + _observations(dossiers, gates, required),
    )


def _validate_gates(
    gates: list[KnowledgeGate],
    dossiers: list[ActorDossier],
    plan: StoryPlan,
    known_events: set[str],
) -> None:
    """Run every gate rule over a list of gates, raising on the first broken one."""
    _validate_gate_anchors(gates, known_events)
    _validate_gate_logic(gates, plan)
    _validate_no_handed_answers(dossiers, gates)
    _validate_premises(gates, dossiers, plan)


def _gate_issue(
    gate: KnowledgeGate,
    gates: list[KnowledgeGate],
    dossiers: list[ActorDossier],
    plan: StoryPlan,
    known_events: set[str],
) -> str:
    """Return the first rule one gate breaks, read against the rest of the bible, or ''."""
    try:
        _validate_gate_anchors([gate], known_events)
        _validate_gate_logic([gate], plan)
        _validate_no_handed_answers(dossiers, [gate])
        _validate_premises(gates, dossiers, plan, only=gate.id)
    except ValueError as exc:
        return str(exc)
    return ""


def _without_future_facts(
    dossier: ActorDossier, future_events: dict[str, set[str]], observations: list[str]
) -> ActorDossier:
    """Drop the initial facts that come from an event at or after the character's first scene.

    7.17: in 20261017-184641 Ilse, still at sea, already knew the ship was stranded on the
    island and its crew declared fallen - the outcome of the second event - and Celestina knew
    the Column was failing before measuring it. The casting declares where each fact comes from,
    and dropping the one from the future is its only correction. Sources that do not line up
    with the facts say nothing, so they are left alone.
    """
    sources = dossier.knowledge_sources
    future = future_events.get(dossier.character_id, set())
    if len(sources) != len(dossier.initial_knowledge) or not future:
        return dossier
    kept = [
        (fact, source)
        for fact, source in zip(dossier.initial_knowledge, sources, strict=True)
        if source.strip() not in future
    ]
    for source in sources:
        if source.strip() in future:
            observations.append(f"fact dropped from {dossier.character_id}: comes from {source}")
    return dossier.model_copy(
        update={
            "initial_knowledge": [fact for fact, _ in kept],
            "knowledge_sources": [source for _, source in kept],
        }
    )


def _revealer_issue(gate: KnowledgeGate, on_stage: dict[str, set[str]] | None) -> str:
    """Say why a gate cannot be revealed in its event because its revealer is absent, or ''.

    Only with typed_clauses (7.17): 3 of the 22 beats forced in the 7.12-7.16 runs needed
    someone who was not in the scene. Whoever brings a fact out has to be there to do it.
    """
    if on_stage is None or not gate.revealed_at_event_id:
        return ""
    present = on_stage.get(gate.revealed_at_event_id, set())
    if gate.revealed_by and gate.revealed_by not in present:
        return (
            f"gate {gate.id} is revealed at {gate.revealed_at_event_id} by {gate.revealed_by}, "
            "who is not on stage in that event's scene"
        )
    if gate.how == "confession" and not present & set(gate.known_by):
        return (
            f"gate {gate.id} is confessed at {gate.revealed_at_event_id}, but nobody who knows "
            "it is on stage in that event's scene"
        )
    return ""


def fallback_bible(cast_ids: list[str], characters: CharactersArtifact) -> CastBible:
    """Derive a thin cast bible from characters.json when the casting stage cannot be run.

    Deterministic and offline: the run continues with a poorer dossier rather than failing, and
    the artifact records that it did.
    """
    by_id = {item.id: item for item in characters.characters}
    dossiers = [
        _dossier_from_profile(by_id[character_id])
        for character_id in dict.fromkeys(cast_ids)
        if character_id in by_id
    ]
    return CastBible(
        dossiers=dossiers,
        knowledge_gates=[],
        observations=["the cast bible was derived from characters.json, not authored"],
        fallback=True,
    )


def gateless(bible: CastBible, plan: StoryPlan) -> bool:
    """Say whether an authored bible leaves a story of several chapters with nothing to learn.

    Found in the 7.12 navigators run: the discovery the whole plot builds to became one
    character's starting secret, with no gate, so it was known from the first scene. Reported,
    not rejected: a story may truly hold no secret, and the run is not worth losing over it.
    """
    return not bible.fallback and not bible.knowledge_gates and len(plan.chapters) > 1


def dossier_index(bible: CastBible) -> dict[str, ActorDossier]:
    """Index one bible's dossiers by character ID."""
    return {item.character_id: item for item in bible.dossiers}


def gates_for(bible: CastBible, character_id: str) -> list[str]:
    """List what one character already knows, so a secret never reaches whoever it hides from."""
    return [gate.fact for gate in bible.knowledge_gates if character_id in set(gate.known_by)]


def _dossier_from_profile(profile: CharacterProfile) -> ActorDossier:
    """Build the minimum playable dossier out of one character profile."""
    return ActorDossier(
        character_id=profile.id,
        public_face=profile.role,
        want=profile.goal or profile.motivation or f"pursue what matters to {profile.name}",
        need=profile.arc,
        wound="",
        fear="",
        moral_line="",
        voice=profile.voice or "speaks plainly",
        behavior_rules=[f"Stay true to this conflict: {profile.conflict}"]
        if profile.conflict
        else [],
        initial_goal=profile.goal,
    )


def _deduplicate(dossiers: list[ActorDossier], known: set[str]) -> list[ActorDossier]:
    """Keep the first dossier per known character and drop the rest."""
    seen: set[str] = set()
    kept: list[ActorDossier] = []
    for item in dossiers:
        if item.character_id not in known or item.character_id in seen:
            continue
        seen.add(item.character_id)
        kept.append(item)
    return kept


def _validate_coverage(dossiers: list[ActorDossier], required: list[str]) -> None:
    """Require one dossier for every character the script puts on stage."""
    missing = [item for item in required if item not in {d.character_id for d in dossiers}]
    if missing:
        raise ValueError(
            f"no dossier for {', '.join(missing)}; every character the script stages needs one, "
            f"and only these IDs may be used: {', '.join(required)}"
        )


def _validate_playable(dossiers: list[ActorDossier]) -> None:
    """Require every dossier to carry something an actor can actually play.

    The correction names each empty field: in 7.12 a repair that only said "a want, a voice or
    a public_face" got back eight dossiers with every public_face blank.
    """
    offenders = []
    for item in sorted(dossiers, key=lambda dossier: dossier.character_id):
        empty = [
            name for name in ("want", "voice", "public_face") if not getattr(item, name).strip()
        ]
        if empty:
            offenders.append(f"{item.character_id} ({', '.join(empty)})")
    if offenders:
        raise ValueError(
            f"these dossiers leave fields empty: {'; '.join(offenders)}; fill them and keep "
            "every other field: a want is a concrete thing the character pursues, a voice says "
            "how they speak, and public_face is what anyone sees of them at a glance"
        )


def _normalize_dossier(dossier: ActorDossier, known: set[str]) -> ActorDossier:
    """Drop references to characters who do not exist, and self-references."""
    relationships: list[ActorRelationship] = []
    seen: set[str] = set()
    for item in dossier.relationships:
        other = item.character_id
        if other not in known or other == dossier.character_id or other in seen:
            continue
        seen.add(other)
        relationships.append(item)
    secret_from = [
        item
        for item in dict.fromkeys(dossier.secret_from)
        if item in known and item != dossier.character_id
    ]
    return dossier.model_copy(update={"relationships": relationships, "secret_from": secret_from})


def _normalize_gates(gates: list[KnowledgeGate], known: set[str]) -> list[KnowledgeGate]:
    """Keep one gate per ID and drop holders who are not characters of this story.

    Two shapes have exactly one correction, so they are corrected (7.14): whoever discovers or
    deduces a fact on stage is taken out of known_by, which keeps the rule that they cannot
    already hold it; and a confession with nobody named as confessor gets its only holder.
    The 7.13 navigators casting lost its whole bible to both in two attempts.
    """
    seen: set[str] = set()
    kept: list[KnowledgeGate] = []
    for gate in gates:
        if gate.id in seen:
            continue
        seen.add(gate.id)
        holders = [item for item in dict.fromkeys(gate.known_by) if item in known]
        revealer = gate.revealed_by if gate.revealed_by in known else ""
        if gate.how in LEARNED_ON_STAGE and revealer in holders:
            holders.remove(revealer)
        if gate.how == "confession" and not revealer and len(holders) == 1:
            revealer = holders[0]
        kept.append(gate.model_copy(update={"known_by": holders, "revealed_by": revealer}))
    return kept


def _validate_gate_anchors(gates: list[KnowledgeGate], known_events: set[str]) -> None:
    """Require every revealing event to be one the validated plan already contains."""
    offenders = sorted(
        {
            gate.revealed_at_event_id
            for gate in gates
            if gate.revealed_at_event_id and gate.revealed_at_event_id not in known_events
        }
    )
    if offenders:
        allowed = ", ".join(sorted(known_events))
        raise ValueError(
            "these knowledge gates are revealed at events that do not exist "
            f"({', '.join(offenders)}); "
            f"use one of the plan's own event IDs or leave it empty: {allowed}"
        )


def _validate_gate_logic(gates: list[KnowledgeGate], plan: StoryPlan) -> None:
    """Keep "who already knows" apart from "who finds out", which the first real run confused.

    That run gave the detective the solution as knowledge she held before the first scene, so
    every deduction she then performed was a recitation. The three rules below make the
    distinction checkable: whoever works a fact out cannot already hold it, whoever confesses
    must, and a reveal has to tell somebody present something they did not know.
    """
    participants = {event.id: set(event.character_ids) for event in plan.events}
    problems: list[str] = []
    for gate in gates:
        holders = set(gate.known_by)
        if gate.how in LEARNED_ON_STAGE and gate.revealed_by in holders:
            problems.append(
                f"gate {gate.id}: {gate.revealed_by} {_LEARNS[gate.how]} this fact on stage, "
                "so they cannot already know it; remove them from known_by"
            )
        if gate.how == "confession" and gate.revealed_by not in holders:
            problems.append(
                f"gate {gate.id}: a confession needs a revealed_by who already knows the fact; "
                "name the confessor and put them in known_by"
            )
        present = participants.get(gate.revealed_at_event_id, set())
        if present and present <= holders:
            problems.append(
                f"gate {gate.id}: everyone present at {gate.revealed_at_event_id} already knows "
                "this fact, so revealing it there tells nobody anything"
            )
    if problems:
        raise ValueError("; ".join(problems))


def _validate_no_handed_answers(dossiers: list[ActorDossier], gates: list[KnowledgeGate]) -> None:
    """Refuse starting knowledge that repeats a fact the same character is meant to work out."""
    by_id = {item.character_id: item for item in dossiers}
    problems: list[str] = []
    for gate in gates:
        if gate.how not in LEARNED_ON_STAGE or gate.revealed_by not in by_id:
            continue
        for item in by_id[gate.revealed_by].initial_knowledge:
            if similarity(item, gate.fact) >= KNOWLEDGE_OVERLAP:
                problems.append(
                    f"{gate.revealed_by} starts out knowing what gate {gate.id} says they "
                    f"{_LEARNS[gate.how]} on stage; remove it from their initial_knowledge"
                )
                break
    if problems:
        raise ValueError("; ".join(problems))


def gates_known_by_discoverer(bible: CastBible) -> int:
    """Count gates whose own discoverer already held them: always 0 once a bible validates."""
    return sum(
        1
        for gate in bible.knowledge_gates
        if gate.how in LEARNED_ON_STAGE and gate.revealed_by in set(gate.known_by)
    )


def _observations(
    dossiers: list[ActorDossier],
    gates: list[KnowledgeGate],
    required: list[str],
) -> list[str]:
    """Report non-blocking findings a usable bible can still carry."""
    observations: list[str] = []
    for item in dossiers:
        if item.secret and not item.secret_from:
            observations.append(f"{item.character_id} keeps a secret from nobody in particular")
        if not item.tactics:
            observations.append(f"{item.character_id} has no tactics to change between")
    for gate in gates:
        if not gate.known_by:
            observations.append(f"gate {gate.id} is known by nobody, so it can only be discovered")
        elif len(gate.known_by) == len(required):
            observations.append(f"gate {gate.id} is known by everyone, so it hides nothing")
    return observations


def _validate_premises(
    gates: list[KnowledgeGate],
    dossiers: list[ActorDossier],
    plan: StoryPlan,
    only: str = "",
) -> None:
    """A deduction needs earlier gates or literal knowledge of its investigator."""
    by_id = {gate.id: gate for gate in gates}
    known = {d.character_id: set(d.initial_knowledge) for d in dossiers}
    order = {event_id: index for index, event_id in enumerate(plan.topological_order)}
    for gate in gates:
        if gate.how != "deduction" or (only and gate.id != only):
            continue
        if not gate.premise_gate_ids and not gate.initial_premises:
            raise ValueError("a deduction needs explicit premise_gate_ids or initial_premises")
        if not set(gate.initial_premises) <= known.get(gate.revealed_by, set()):
            raise ValueError(
                "initial deduction premises must belong to the investigator's initial knowledge"
            )
        for key in gate.premise_gate_ids:
            prior = by_id.get(key)
            if prior is None or key == gate.id:
                raise ValueError("deduction premise references an unknown or identical gate")
            if gate.revealed_by not in prior.known_by and order.get(
                prior.revealed_at_event_id, len(order)
            ) >= order.get(gate.revealed_at_event_id, -1):
                raise ValueError("deduction premises must be revealed before their conclusion")
