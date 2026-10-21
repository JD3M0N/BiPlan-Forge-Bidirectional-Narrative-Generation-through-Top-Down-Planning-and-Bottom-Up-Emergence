"""Shared reader orientation rules and evidence-backed chapter memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from .anchoring import quoted

ORIENTATION_RULES = (
    " Reader orientation: at a character's first actual appearance, briefly establish who "
    "they are (species, public occupation or relationship when relevant) and one distinctive "
    "visible trait, using only supplied public facts. A passing mention needs no introduction. "
    "At a new place establish its kind and one or two details that help picture the action. "
    "Integrate this in action, usually in one sentence; do not paste a dossier. Do not repeat "
    "introductions already evidenced in READER CONTEXT. When a character changes location, "
    "make an otherwise unclear departure, arrival or time ellipsis legible. Only express a "
    "recorded or unambiguously implicit transfer; never invent a route, escape, vehicle or "
    "journey outcome. Obvious adjacent moves need no explanation. A cut to a different group "
    "is a parallel scene, not their journey: orient with place/time as appropriate. Preserve "
    "mystery, secrets and the narrator's knowledge limits. A location heading alone does not "
    "explain how someone arrived."
)

SPATIAL_RULES = (
    " Check physical continuity against the current setting and established action: a person "
    "or fixed object cannot be in two places without an established transfer. A ship's helm "
    "cannot be used inside a temple merely because its captain is there. Distinguish literal "
    "actions from memories, metaphors and intentions. A recorded arrival updates the opening "
    "setting: use the latest established position. Personal portable belongings can travel "
    "with their holder; do not require an inventory entry for every ordinary detail. Flag "
    "incompatible locations or unavailable fixed objects at their source, with evidence; never "
    "repair them by inventing a journey."
)

EVIDENCE_RULES = (
    " Return reader_evidence only for information actually established in this chapter's "
    "prose, not intended by the source. Each item needs a supplied entity_id and an exact "
    "quote of at least four words from this chapter. character evidence must establish public "
    "identity/context, not merely a name or action; place evidence must describe the space, "
    "not merely name it. position evidence identifies a character's last established location "
    "in the prose, using a supplied location_id. Never count an offstage mention as an "
    "introduction. Omit unsupported items."
)

ORIENTATION_CODES = frozenset({"CHARACTER_CONTEXT", "PLACE_CONTEXT", "MISSING_TRANSITION"})


class ReaderEvidence(BaseModel):
    """One public introduction or position supported by final prose."""

    kind: Literal["character", "place", "position"]
    entity_id: str
    quote: str
    location_id: str = ""


class ReaderSnapshot(BaseModel):
    """Optional observations keep older review artifacts readable."""

    reader_evidence: list[ReaderEvidence] = Field(default_factory=list)


@dataclass
class ReaderState:
    """Remember only descriptions and positions evidenced in accepted chapters."""

    characters: dict[str, dict] = field(default_factory=dict)
    places: dict[str, dict] = field(default_factory=dict)
    positions: dict[str, dict] = field(default_factory=dict)

    def accept(self, evidence, body: str, context: dict, chapter: int) -> None:
        """Reject absent quotes and unknown entities before updating accumulated memory."""
        characters = {item["id"] for item in context.get("characters", [])}
        places = {item["id"] for item in context.get("places", [])}
        for item in evidence:
            if not quoted(item.quote, body):
                continue
            record = {"quote": item.quote, "chapter": chapter}
            if item.kind == "character" and item.entity_id in characters:
                self.characters.setdefault(item.entity_id, record)
            elif item.kind == "place" and item.entity_id in places:
                self.places.setdefault(item.entity_id, record)
            elif (
                item.kind == "position"
                and item.entity_id in characters
                and item.location_id in places
            ):
                self.positions[item.entity_id] = {**record, "location_id": item.location_id}

    def as_record(self) -> dict:
        """Expose public reader knowledge, with quotes available for later review."""
        return {"characters": self.characters, "places": self.places, "positions": self.positions}


def narrative_context(characters, world, events, state: ReaderState) -> dict:
    """Supply planned context without treating plans as previously narrated facts."""
    return {
        "characters": [
            {"id": c.id, "name": c.name, "public_context": c.role} for c in characters.characters
        ],
        "places": [
            {"id": p.id, "name": p.name, "description": p.description} for p in world.locations
        ]
        if world
        else [],
        "source_events": [event.model_dump(mode="json") for event in events],
        "reader": state.as_record(),
    }


def performance_context(visible, play, bible, world, state: ReaderState) -> dict:
    """Limit context to visible scenes and public faces, never actor secrets or future plans."""
    from ..stage.selection import script_scenes

    scenes = script_scenes(play)
    scene_ids = list(dict.fromkeys(turn.scene_id for turn in visible))
    selected = [scenes[key] for key in scene_ids if key in scenes]
    ids = {member.character_id for scene in selected for member in scene.cast}
    faces = {d.character_id: d.public_face for d in bible.dossiers} if bible else {}
    locations = {p.id: p for p in world.locations} if world else {}
    return {
        "characters": [
            {"id": c.character_id, "name": c.name, "public_context": faces.get(c.character_id, "")}
            for c in play.cast
            if c.character_id in ids
        ],
        "places": [
            {
                "id": s.location_id or s.id,
                "name": locations[s.location_id].name if s.location_id in locations else "",
                "description": s.setting,
            }
            for s in selected
        ],
        "scenes": [
            {
                "id": s.id,
                "location_id": s.location_id or s.id,
                "setting": s.setting,
                "cast": [c.character_id for c in s.cast],
            }
            for s in selected
        ],
        "reader": state.as_record(),
    }
