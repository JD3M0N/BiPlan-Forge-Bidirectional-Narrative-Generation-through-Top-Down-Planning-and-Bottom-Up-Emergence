from pydantic import BaseModel, Field

from .base import Agent, json_text
from ..schemas import (
    CharacterProfile, CharacterRelationship, CharactersArtifact, SliderRange,
    StoryPlanArtifact, StoryRequest, TaxonomyBrief, WorldArtifact,
)


class CharacterSliderArcDraft(BaseModel):
    sympathy: SliderRange
    competence: SliderRange
    proactivity: SliderRange
    focus: str
    arc_type: str
    steadfast_truth: str | None = None
    world_change: str | None = None
    justification: str = Field(min_length=1)


class CharacterProfileDraft(CharacterProfile):
    slider_arc: CharacterSliderArcDraft | None = None


class CharactersDraft(BaseModel):
    characters: list[CharacterProfileDraft] = Field(min_length=1)
    relationships: list[CharacterRelationship] = Field(default_factory=list)


def _normalize_slider_arc(character: dict) -> None:
    arc = character.get("slider_arc")
    if not arc and character.get("importance") == "main":
        arc = {
            "sympathy": {"start": 4, "target": 7, "rationale": "Observable growth"},
            "competence": {"start": 7, "target": 7, "rationale": "Stable strength"},
            "proactivity": {"start": 7, "target": 7, "rationale": "Stable strength"},
            "focus": "sympathy", "arc_type": "positive",
            "justification": "The internal change becomes observable in behavior",
        }
        character["slider_arc"] = arc
    if not arc:
        return
    names = ("sympathy", "competence", "proactivity")
    focus = arc.get("focus") if arc.get("focus") in names else "sympathy"
    arc["focus"] = focus
    arc_type = arc.get("arc_type") if arc.get("arc_type") in {
        "positive", "negative", "flat",
    } else "positive"
    arc["arc_type"] = arc_type
    if arc_type == "positive":
        arc[focus]["start"] = min(4, arc[focus]["start"])
        arc[focus]["target"] = max(7, arc[focus]["target"])
        for name in names:
            if name != focus:
                arc[name]["start"] = max(6, arc[name]["start"])
                arc[name]["target"] = max(6, arc[name]["target"])
    elif arc_type == "negative":
        arc[focus]["start"] = max(4, arc[focus]["start"])
        arc[focus]["target"] = min(arc[focus]["target"], arc[focus]["start"] - 3)
        if max(arc[name]["target"] for name in names) < 6:
            strongest = max((name for name in names if name != focus),
                            key=lambda name: arc[name]["target"])
            arc[strongest]["target"] = 6
    else:
        strongest = sorted(names, key=lambda name: arc[name]["start"], reverse=True)[:2]
        for name in strongest:
            arc[name]["start"] = max(6, arc[name]["start"])
        for name in names:
            start = arc[name]["start"]
            arc[name]["target"] = min(start + 1, max(start - 1, arc[name]["target"]))
        arc["steadfast_truth"] = arc.get("steadfast_truth") or (
            "The character remains committed to the stated personal rule"
        )
        arc["world_change"] = arc.get("world_change") or (
            "That commitment produces an observable change in the story world"
        )


class CharacterDesignerAgent(Agent[CharactersArtifact]):
    name = "characters"

    def run(
        self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact,
        repair_feedback: str = "",
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> CharactersArtifact:
        draft = self.provider.generate_structured(
            system_instruction=(
                "Create a compact cast with distinct goals. Every important action must follow a "
                "character intention, and opposition must pursue an active incompatible goal. Use "
                "retrieved roles as flexible archetype inspiration and mark at least one character as main. "
                "Give stable lowercase IDs and valid initial world locations. Complete role, ensemble seat, "
                "competence domain, want, need, misbelief, wound, related strength/flaw and its concrete cost, "
                "personal rule, voice, and noticed details. Main characters may have positive, negative, or "
                "flat Sanderson slider arcs. For a positive arc, the focused slider starts at 4 or less "
                "and ends at 7 or more while both other sliders start and end at 6 or more. For a negative "
                "arc, the focus falls by at least 3 and at least one final slider is 6 or more. For a flat "
                "arc, every slider changes by at most 1, at least two start at 6 or more, and steadfast_truth "
                "plus world_change are mandatory. Obey these schema invariants. "
                "Represent every relationship with canonical source/target character IDs, kind, and current state. "
                "Supporting characters may omit slider arcs. Return all artifact text in English "
                "regardless of the requested fiction language."
            ),
            prompt=(f"NORMALIZED SPECIFICATION:\n{json_text(request.agent_spec())}\n\nPLAN:\n{json_text(plan)}"
                    f"\n\nWORLD:\n{json_text(world)}\n\nTAXONOMY ROLE PALETTE:\n"
                    f"{json_text(taxonomy_brief.roles) if taxonomy_brief else 'none'}"
                    f"\n\nTAXONOMY USAGE RULE:\n"
                    f"{taxonomy_brief.usage_rule if taxonomy_brief else 'Use roles flexibly.'}"
                    f"{repair_feedback}"),
            schema=CharactersDraft,
        )
        payload = draft.model_dump(mode="json")
        for character in payload["characters"]:
            _normalize_slider_arc(character)
        return CharactersArtifact.model_validate(payload)
