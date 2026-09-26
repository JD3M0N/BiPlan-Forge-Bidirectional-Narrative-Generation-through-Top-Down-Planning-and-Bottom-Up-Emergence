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


def materialize_bible(
    draft: CastBibleDraft,
    *,
    cast_ids: list[str],
    characters: CharactersArtifact,
    plan: StoryPlan,
) -> CastBible:
    """Validate one proposed cast bible and mint the trusted version."""
    known_characters = {item.id for item in characters.characters}
    known_events = {event.id for event in plan.events}
    required = list(dict.fromkeys(cast_ids))

    dossiers = _deduplicate(draft.dossiers, known_characters)
    _validate_coverage(dossiers, required)
    _validate_playable(dossiers)
    dossiers = [_normalize_dossier(item, known_characters) for item in dossiers]

    gates = _normalize_gates(draft.knowledge_gates, known_characters)
    _validate_gate_anchors(gates, known_events)

    return CastBible(
        dossiers=dossiers,
        knowledge_gates=gates,
        observations=_observations(dossiers, gates, required),
    )


def fallback_bible(cast_ids: list[str], characters: CharactersArtifact) -> CastBible:
    """Derive a thin cast bible from characters.json when the casting stage cannot be run.

    Deterministic and offline, like the escape room's backup narrator: the run continues with a
    poorer dossier rather than failing, and the artifact records that it did.
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
    """Require every dossier to carry something an actor can actually play."""
    offenders = [
        item.character_id for item in dossiers if not item.want.strip() or not item.voice.strip()
    ]
    if offenders:
        raise ValueError(
            f"the dossiers for {', '.join(sorted(offenders))} have no playable want or no voice; "
            "a want is a concrete thing the character pursues and a voice says how they speak"
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
    """Keep one gate per ID and drop holders who are not characters of this story."""
    seen: set[str] = set()
    kept: list[KnowledgeGate] = []
    for gate in gates:
        if gate.id in seen:
            continue
        seen.add(gate.id)
        holders = [item for item in dict.fromkeys(gate.known_by) if item in known]
        kept.append(gate.model_copy(update={"known_by": holders}))
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
