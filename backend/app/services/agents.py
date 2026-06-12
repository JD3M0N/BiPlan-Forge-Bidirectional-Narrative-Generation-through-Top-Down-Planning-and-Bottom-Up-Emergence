import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.schemas import (
    ArchitectOutline,
    ChapterDraft,
    ChapterDraftBatch,
    ChapterPlanItem,
    ContextSummary,
    DependencyReview,
    DirectorPlan,
    DramaRevision,
    FinalStory,
    PlotWeave,
    PlanningRoomResult,
    SimulationLog,
    StoryPacket,
    StoryEvaluation,
    WorldBible,
)

T = TypeVar("T", bound=BaseModel)


class StoryAgents:
    def __init__(self, llm_client) -> None:
        self.llm_client = llm_client

    async def run_architect(self, packet: StoryPacket) -> ArchitectOutline:
        prompt = f"""
You are The Architect in a multi-agent story room.
Return strict JSON only.
Build a top-down narrative skeleton from this user brief. Include event seeds that can later become a DAG:
{json.dumps(packet.input_brief, ensure_ascii=False, indent=2)}

Required JSON shape:
{{
  "premise": "string",
  "synopsis": "string",
  "beats": [{{"title": "string", "purpose": "string", "stakes": "string"}}],
  "seed_events": [
    {{
      "id": "E1",
      "summary": "string",
      "purpose": "string",
      "characters": ["string"],
      "dependencies": ["E0"]
    }}
  ],
  "climax": "string",
  "resolution": "string"
}}
"""
        return await self._generate_structured(prompt, ArchitectOutline)

    async def run_world_builder(self, packet: StoryPacket) -> WorldBible:
        prompt = f"""
You are The World Builder.
Return strict JSON only.
Expand the story outline with grounded lore, character motivations, locations, objects, world rules,
an initial state, and lightweight entity relations for an in-memory NEKG.

Current packet:
{self._packet_json(packet)}

Required JSON shape:
{{
  "characters": [
    {{"name": "string", "role": "string", "description": "string", "desire": "string", "fear": "string"}}
  ],
  "locations": [
    {{"name": "string", "description": "string", "mood": "string"}}
  ],
  "objects": [
    {{"name": "string", "significance": "string"}}
  ],
  "rules": ["string"],
  "initial_state": "string",
  "entity_relations": [
    {{"source": "string", "relation": "string", "target": "string"}}
  ]
}}
"""
        return await self._generate_structured(prompt, WorldBible)

    async def run_director(self, packet: StoryPacket) -> DirectorPlan:
        prompt = f"""
You are The Director.
Return strict JSON only.
Use indirect narrative direction: never force a character action. Create abstract acts and environmental
interventions that pressure autonomous characters through setting, objects, information, or contextual events.

Current packet:
{self._packet_json(packet)}

Required JSON shape:
{{
  "acts": [
    {{
      "abstract_act": "string",
      "purpose": "string",
      "target_event_ids": ["E1"],
      "environmental_intervention": "string",
      "expected_pressure": "string"
    }}
  ],
  "constraints": ["string"]
}}
"""
        return await self._generate_structured(prompt, DirectorPlan)

    async def run_character_simulator(self, packet: StoryPacket) -> SimulationLog:
        prompt = f"""
You are The Character Simulator.
Return strict JSON only.
Simulate bottom-up character intentions and plausible actions using memory, reflection, world rules,
and the Director's indirect interventions. Do not write prose; write simulation logs.

Current packet:
{self._packet_json(packet)}

Required JSON shape:
{{
  "actions": [
    {{
      "character": "string",
      "event_id": "E1",
      "intention": "string",
      "action": "string",
      "memory_used": "string",
      "reflection": "string",
      "world_delta": "string"
    }}
  ],
  "memory_updates": ["string"]
}}
"""
        return await self._generate_structured(prompt, SimulationLog)

    async def run_plot_weaver(self, packet: StoryPacket, chapter_count: int) -> PlotWeave:
        prompt = f"""
You are The Plot Weaver.
Return strict JSON only.
Fuse top-down event seeds and bottom-up simulation logs into a coherent DAG. Use SVO triplets for each
event, keep dependencies acyclic, produce a lightweight NEKG as entity relations, and plan exactly
{chapter_count} chapters.

Current packet:
{self._packet_json(packet)}

Required JSON shape:
{{
  "event_graph": [
    {{
      "id": "E1",
      "summary": "string",
      "svo": {{"subject": "string", "verb": "string", "object": "string"}},
      "characters": ["string"],
      "location": "string",
      "time": "string",
      "dependencies": ["E0"],
      "dramatic_role": "setup|turn|climax|resolution"
    }}
  ],
  "entity_graph": [
    {{"source": "string", "relation": "string", "target": "string"}}
  ],
  "chapter_plan": {{
    "chapters": [
      {{
        "index": 1,
        "title": "string",
        "abstract": "string",
        "event_ids": ["E1"],
        "target_words": 800
      }}
    ],
    "narrative_order": ["E1"]
  }}
}}
"""
        return await self._generate_structured(prompt, PlotWeave)

    async def run_planning_room(self, packet: StoryPacket, chapter_count: int) -> PlanningRoomResult:
        prompt = f"""
You are The Planning Room: The Architect, The World Builder, The Director, The Character Simulator,
The Plot Weaver, The Drama Coach, and The Dependency Manager working together.
Return strict JSON only.
Build the complete non-prose planning packet in one pass to minimize API calls. Preserve the responsibilities
of each agent: top-down outline, grounded lore, indirect direction, character simulation, acyclic event DAG,
dramatic revision, and continuity review. Plan exactly {chapter_count} chapters.

User brief:
{json.dumps(packet.input_brief, ensure_ascii=False, indent=2)}

Required JSON shape:
{{
  "architect_outline": {{
    "premise": "string",
    "synopsis": "string",
    "beats": [{{"title": "string", "purpose": "string", "stakes": "string"}}],
    "seed_events": [
      {{"id": "E1", "summary": "string", "purpose": "string", "characters": ["string"], "dependencies": []}}
    ],
    "climax": "string",
    "resolution": "string"
  }},
  "world_bible": {{
    "characters": [
      {{"name": "string", "role": "string", "description": "string", "desire": "string", "fear": "string"}}
    ],
    "locations": [{{"name": "string", "description": "string", "mood": "string"}}],
    "objects": [{{"name": "string", "significance": "string"}}],
    "rules": ["string"],
    "initial_state": "string",
    "entity_relations": [{{"source": "string", "relation": "string", "target": "string"}}]
  }},
  "director_plan": {{
    "acts": [
      {{
        "abstract_act": "string",
        "purpose": "string",
        "target_event_ids": ["E1"],
        "environmental_intervention": "string",
        "expected_pressure": "string"
      }}
    ],
    "constraints": ["string"]
  }},
  "simulation_log": {{
    "actions": [
      {{
        "character": "string",
        "event_id": "E1",
        "intention": "string",
        "action": "string",
        "memory_used": "string",
        "reflection": "string",
        "world_delta": "string"
      }}
    ],
    "memory_updates": ["string"]
  }},
  "event_graph": [
    {{
      "id": "E1",
      "summary": "string",
      "svo": {{"subject": "string", "verb": "string", "object": "string"}},
      "characters": ["string"],
      "location": "string",
      "time": "string",
      "dependencies": [],
      "dramatic_role": "setup|turn|climax|resolution"
    }}
  ],
  "entity_graph": [{{"source": "string", "relation": "string", "target": "string"}}],
  "chapter_plan": {{
    "chapters": [
      {{"index": 1, "title": "string", "abstract": "string", "event_ids": ["E1"], "target_words": 800}}
    ],
    "narrative_order": ["E1"]
  }},
  "drama_revision": {{
    "revised_beats": [{{"title": "string", "purpose": "string", "stakes": "string"}}],
    "tension_notes": ["string"],
    "character_arc_notes": ["string"],
    "pacing_notes": ["string"],
    "suspense_devices": ["string"]
  }},
  "dependency_review": {{
    "is_consistent": true,
    "issues": ["string"],
    "fixes_applied": ["string"],
    "narrator_guidance": ["string"],
    "dependency_notes": ["string"]
  }}
}}
"""
        return await self._generate_structured(prompt, PlanningRoomResult)

    async def run_drama_coach(self, packet: StoryPacket) -> DramaRevision:
        prompt = f"""
You are The Drama Coach.
Return strict JSON only.
Analyze the current packet and make the story more dramatic without breaking its internal logic.
Focus on tension, character arcs, suspense devices, and pacing.

Current packet:
{self._packet_json(packet)}

Required JSON shape:
{{
  "revised_beats": [{{"title": "string", "purpose": "string", "stakes": "string"}}],
  "tension_notes": ["string"],
  "character_arc_notes": ["string"],
  "pacing_notes": ["string"],
  "suspense_devices": ["string"]
}}
"""
        return await self._generate_structured(prompt, DramaRevision)

    async def run_dependency_manager(self, packet: StoryPacket) -> DependencyReview:
        prompt = f"""
You are The Dependency Manager.
Return strict JSON only.
Review continuity, causality and character consistency. If needed, propose fixes and narrator guidance.

Current packet:
{self._packet_json(packet)}

Required JSON shape:
{{
  "is_consistent": true,
  "issues": ["string"],
  "fixes_applied": ["string"],
  "narrator_guidance": ["string"],
  "dependency_notes": ["string"]
}}
"""
        return await self._generate_structured(prompt, DependencyReview)

    async def run_coordinator(self, packet: StoryPacket, chapter: ChapterPlanItem) -> ContextSummary:
        prompt = f"""
You are The Coordinator/ReIO.
Return strict JSON only.
Compress only the relevant story history for the next chapter. Preserve continuity facts, event dependencies,
character memory, and style constraints. Do not write the chapter.

Current packet:
{self._packet_json(packet)}

Target chapter index: {chapter.index}

Next chapter:
{json.dumps(chapter.dict(), ensure_ascii=False, indent=2)}

Required JSON shape:
{{
  "chapter_index": 1,
  "relevant_events": ["E1"],
  "summary": "string",
  "continuity_constraints": ["string"]
}}
"""
        return await self._generate_structured(prompt, ContextSummary)

    async def run_chapter_writer(self, packet: StoryPacket, context: ContextSummary) -> ChapterDraft:
        prompt = f"""
You are The Chapter Writer.
Return strict JSON only.
Write polished prose in the requested language and style for exactly one chapter. Follow the Coordinator/ReIO
context, event graph, dependency review, and drama notes. Keep chapter text self-contained and coherent.

Current packet:
{self._packet_json(packet)}

Target chapter index: {context.chapter_index}

Coordinator/ReIO context:
{json.dumps(context.dict(), ensure_ascii=False, indent=2)}

Required JSON shape:
{{
  "chapter_index": 1,
  "title": "string",
  "text": "string",
  "rewritten": false,
  "notes": ["string"]
}}
"""
        return await self._generate_structured(prompt, ChapterDraft)

    async def run_chapter_writer_batch(self, packet: StoryPacket) -> ChapterDraftBatch:
        prompt = f"""
You are The Chapter Writer Batch.
Return strict JSON only.
Write polished prose in the requested language and style for every chapter in the chapter plan. Follow the
event graph, dependency review, drama notes, world rules, and continuity constraints. Return one draft per
planned chapter and keep chapter indexes aligned with the plan.

Current packet:
{self._packet_json(packet)}

Required JSON shape:
{{
  "chapters": [
    {{
      "chapter_index": 1,
      "title": "string",
      "text": "string",
      "rewritten": false,
      "notes": ["string"]
    }}
  ]
}}
"""
        return await self._generate_structured(prompt, ChapterDraftBatch)

    async def run_quality_evaluator(self, packet: StoryPacket) -> StoryEvaluation:
        prompt = f"""
You are The Quality Evaluator.
Return strict JSON only.
Evaluate the generated story using HANNA dimensions plus LitVISTA-inspired orchestration.
Use scores from 0 to 5. Add blocking issues only for contradictions or severe incoherence that require rewriting.

Current packet:
{self._packet_json(packet)}

Required JSON shape:
{{
  "relevance": 4.0,
  "coherence": 4.0,
  "empathy": 4.0,
  "surprise": 4.0,
  "engagement": 4.0,
  "complexity": 4.0,
  "orchestration": 4.0,
  "overall": 4.0,
  "blocking_issues": ["string"],
  "notes": ["string"]
}}
"""
        return await self._generate_structured(prompt, StoryEvaluation)

    async def run_quality_rewriter(self, packet: StoryPacket) -> FinalStory:
        prompt = f"""
You are The Quality Rewriter.
Return strict JSON only.
Rewrite the compiled story once to resolve blocking quality issues while preserving chapter headings,
the event DAG, character autonomy, style, language, and all continuity constraints.

Current packet:
{self._packet_json(packet)}

Required JSON shape:
{{
  "title": "string",
  "summary": "string",
  "story_text": "string"
}}
"""
        return await self._generate_structured(prompt, FinalStory)

    async def run_narrator(self, packet: StoryPacket) -> FinalStory:
        return await self.run_quality_rewriter(packet)

    async def _generate_structured(self, prompt: str, model_type: type[T]) -> T:
        payload = await self.llm_client.generate_json(prompt)
        try:
            return model_type.parse_obj(payload)
        except ValidationError as exc:
            raise RuntimeError(f"Invalid payload for {model_type.__name__}: {exc}") from exc

    def _packet_json(self, packet: StoryPacket) -> str:
        return json.dumps(packet.dict(exclude_none=True), ensure_ascii=False, indent=2)
