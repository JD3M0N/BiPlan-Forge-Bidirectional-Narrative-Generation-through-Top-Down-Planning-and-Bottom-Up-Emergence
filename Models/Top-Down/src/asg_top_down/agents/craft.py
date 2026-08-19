"""Independent modular craft planners plus prose critic and rewriter."""

from __future__ import annotations

import json

from .base import Agent, json_text
from ..craft import audit_questions, normalize_audit, try_fail_target
from ..schemas import (
    ChapterPPPPlan, ChapterPlan, CharactersArtifact, CharacterArcPlan,
    CraftAuditArtifact, GlobalPPPPlan, IncrementalStorylineArtifact,
    StoryCraftPlan, StoryOutlineArtifact, StoryPlanArtifact, StoryRequest,
    StorylineObligation, TaxonomyBrief, TryFailPlan, WorldArtifact,
)


class GlobalPPPPlannerAgent(Agent[GlobalPPPPlan]):
    name = "global_ppp"

    def run(
        self, request: StoryRequest, plan: StoryPlanArtifact, world: WorldArtifact,
        characters: CharactersArtifact, outline: StoryOutlineArtifact,
        repair_feedback: str = "", taxonomy_brief: TaxonomyBrief | None = None,
    ) -> GlobalPPPPlan:
        return self.provider.generate_structured(
            system_instruction=(
                "Design one authoritative global Promise-Progress-Payoff plan before STORYLINE. "
                "Include a tone promise, exactly one primary line, and zero to two supporting plot, "
                "character, or relationship lines. Every line needs one promise, at least one visible "
                "conflict-bearing progress signal, and one prepared, fulfilling, potentially surprising "
                "payoff. Give every point a stable descriptive ID and schedule at least one global point "
                "in every chapter. The primary promise starts in the first chapter and its payoff occurs "
                "in the final chapter. Use chapter IDs and natural-language events only. Return all "
                "artifact text in English."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}"
                f"\n\nWORLD:\n{json_text(world)}\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nOUTLINE:\n{json_text(outline)}"
                f"\n\nTAXONOMY BRIEF:\n{json_text(taxonomy_brief) if taxonomy_brief else 'none'}"
                f"{repair_feedback}"
            ),
            schema=GlobalPPPPlan,
        )


class CharacterArcPlannerAgent(Agent[CharacterArcPlan]):
    name = "character_arcs"

    def run(
        self, characters: CharactersArtifact, outline: StoryOutlineArtifact,
        global_ppp: GlobalPPPPlan, repair_feedback: str = "",
    ) -> CharacterArcPlan:
        return self.provider.generate_structured(
            system_instruction=(
                "Plan observable character craft independently from PPP. For every main character, "
                "create exactly start, transition, and end milestones for the already selected "
                "low-to-high focus slider. Schedule them in nondecreasing chapter order and make the "
                "change affect consequential choices that support the global PPP. Return English text."
            ),
            prompt=(
                f"CHARACTERS:\n{json_text(characters)}\n\nOUTLINE:\n{json_text(outline)}"
                f"\n\nGLOBAL PPP:\n{json_text(global_ppp)}{repair_feedback}"
            ),
            schema=CharacterArcPlan,
        )


class TryFailPlannerAgent(Agent[TryFailPlan]):
    name = "try_fail"

    def run(
        self, request: StoryRequest, outline: StoryOutlineArtifact,
        global_ppp: GlobalPPPPlan, repair_feedback: str = "",
    ) -> TryFailPlan:
        count = try_fail_target(request.target_words)
        return self.provider.generate_structured(
            system_instruction=(
                "Plan exactly the requested number of independent Yes-but or No-and cycles. Each "
                "attempt must advance a global promise through conflict, change the terms of the "
                "problem, and have a persistent consequence. Use chapter IDs and English text."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nOUTLINE:\n{json_text(outline)}"
                f"\n\nGLOBAL PPP:\n{json_text(global_ppp)}"
                f"\n\nEXACT CYCLE COUNT: {count}{repair_feedback}"
            ),
            schema=TryFailPlan,
        )


class ChapterPPPPlannerAgent(Agent[ChapterPPPPlan]):
    name = "chapter_ppp"

    def run(
        self, global_ppp: GlobalPPPPlan, chapter: ChapterPlan,
        storyline: IncrementalStorylineArtifact,
        chapter_obligations: list[StorylineObligation],
        previous: ChapterPPPPlan | None = None, repair_feedback: str = "",
    ) -> ChapterPPPPlan:
        nodes = [node for node in storyline.nodes if node.chapter_id == chapter.id]
        return self.provider.generate_structured(
            system_instruction=(
                "Ground one chapter-level Promise-Progress-Payoff line in the immutable accepted "
                "STORYLINE. Establish a local expectation, signal progress through conflict, and "
                "resolve or consequentially transform it. Reference only supplied node IDs from this "
                "chapter, in event order. Include every global PPP point scheduled for the chapter in "
                "advances_global_point_ids. Do not invent, alter, or reorder facts. Return English text."
            ),
            prompt=(
                f"GLOBAL PPP:\n{json_text(global_ppp)}\n\nCHAPTER:\n{json_text(chapter)}"
                f"\n\nACCEPTED CHAPTER NODES:\n{json_text(nodes)}"
                f"\n\nCHAPTER OBLIGATIONS:\n{json_text(chapter_obligations)}"
                f"\n\nPREVIOUS CHAPTER PPP:\n{json_text(previous) if previous else 'none'}"
                f"{repair_feedback}"
            ),
            schema=ChapterPPPPlan,
        )


class CraftCriticAgent(Agent[CraftAuditArtifact]):
    name = "craft_critic"

    def run(
        self, request: StoryRequest, craft: StoryCraftPlan,
        characters: CharactersArtifact, outline: StoryOutlineArtifact,
        storyline: IncrementalStorylineArtifact, draft: str,
        taxonomy_brief: TaxonomyBrief | None = None,
    ) -> CraftAuditArtifact:
        questions = audit_questions(request, craft, characters, taxonomy_brief)
        raw = self.provider.generate_structured(
            system_instruction=(
                "You are a demanding story-craft critic. Answer every supplied question exactly once "
                "using its exact metadata. Judge fiction rather than planning labels and cite concise "
                "location-specific evidence. Failures require actionable issues and revision instructions. "
                "Use not_applicable only for non-blocking questions. Write analysis in English, assign "
                "no scores, and invent no questions."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nMODULAR CRAFT:\n{json_text(craft)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}\n\nOUTLINE:\n{json_text(outline)}"
                f"\n\nSTORYLINE:\n{json_text(storyline)}"
                f"\n\nTAXONOMY BRIEF:\n{json_text(taxonomy_brief) if taxonomy_brief else 'none'}"
                f"\n\nQUESTIONS:\n{json.dumps(questions, ensure_ascii=False, indent=2)}"
                f"\n\nFICTION:\n{draft}"
            ),
            schema=CraftAuditArtifact,
        )
        return normalize_audit(raw, questions)


class CraftRewriterAgent(Agent[str]):
    name = "craft_rewriter"

    def run(
        self, request: StoryRequest, craft: StoryCraftPlan,
        characters: CharactersArtifact, outline: StoryOutlineArtifact,
        storyline: IncrementalStorylineArtifact, draft: str, audit: CraftAuditArtifact,
        length_instruction: str = "", taxonomy_brief: TaxonomyBrief | None = None,
    ) -> str:
        failed = sorted(
            (answer for answer in audit.answers if answer.verdict == "fail"),
            key=lambda answer: not answer.blocking,
        )
        return self.provider.generate_text(
            system_instruction=(
                "You are a literary rewriter. Rewrite the complete fiction once, applying every failed "
                "audit instruction. Preserve accepted facts, causal dependencies, event outcomes, user "
                f"constraints, the output language ({request.language}), headings, and approximate length. "
                "Realize global and chapter PPP, character growth, and try-fail consequences through "
                "action and choice. Never expose IDs, questions, taxonomy, or planning terminology. "
                "Return only the complete revised story in Markdown with canonical chapter headings."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nMODULAR CRAFT:\n{json_text(craft)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}\n\nOUTLINE:\n{json_text(outline)}"
                f"\n\nSTORYLINE:\n{json_text(storyline)}"
                f"\n\nTAXONOMY BRIEF:\n{json_text(taxonomy_brief) if taxonomy_brief else 'none'}"
                f"\n\nFAILED AUDIT ANSWERS:\n"
                f"{json.dumps([answer.model_dump(mode='json') for answer in failed], ensure_ascii=False, indent=2)}"
                f"\n\nDETERMINISTIC LENGTH INSTRUCTION:\n{length_instruction or 'none'}"
                f"\n\nDRAFT:\n{draft}"
            ),
        )
