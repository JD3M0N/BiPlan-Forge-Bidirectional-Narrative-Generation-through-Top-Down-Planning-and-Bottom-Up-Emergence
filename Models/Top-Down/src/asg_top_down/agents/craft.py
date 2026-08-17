"""Agents for independent post-STORYLINE craft planning and prose review."""

from __future__ import annotations

import json

from .base import Agent, json_text
from ..craft import audit_questions, normalize_audit, try_fail_target
from ..schemas import (
    CharactersArtifact, CraftAuditArtifact, CraftSelectionArtifact, CraftVariant,
    CraftVariantsArtifact, IncrementalStorylineArtifact, StoryOutlineArtifact,
    StoryPlanArtifact, StoryRequest, WorldArtifact,
)


class CraftVariantPlannerAgent(Agent[CraftVariantsArtifact]):
    name = "craft_variants"

    def run(
        self,
        request: StoryRequest,
        plan: StoryPlanArtifact,
        world: WorldArtifact,
        characters: CharactersArtifact,
        outline: StoryOutlineArtifact,
        storyline: IncrementalStorylineArtifact,
        repair_feedback: str = "",
    ) -> CraftVariantsArtifact:
        cycles = try_fail_target(request.target_words)
        return self.provider.generate_structured(
            system_instruction=(
                "Design exactly three substantially different post-STORYLINE craft variants named "
                "variant-1, variant-2, and variant-3. Each variant needs one master "
                "promise-progress-payoff line spanning the first through final chapter, zero to two "
                "complete global subplots, and exactly one local promise-progress-payoff line for every "
                "chapter. Every local line must identify which global line it advances. For every main "
                "character, create observable start, transition, and end milestones for the already "
                "chosen low-to-high focus slider. Add exactly the supplied number of Yes-but or No-and "
                "cycles with persistent consequences. Fit all guidance to accepted events without "
                "changing causal facts. Refer only to chapter IDs and natural-language events: never "
                "include plot-node IDs or the terms CBN, CPN, or CEN. Promise means reader expectation; "
                "progress means meaningful signposting; payoff must be surprising but prepared."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}"
                f"\n\nWORLD:\n{json_text(world)}\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nOUTLINE:\n{json_text(outline)}\n\nACCEPTED STORYLINE:\n{json_text(storyline)}"
                f"\n\nEXACT TRY-FAIL COUNT PER VARIANT: {cycles}{repair_feedback}"
            ),
            schema=CraftVariantsArtifact,
        )


class CraftVariantSelectorAgent(Agent[CraftSelectionArtifact]):
    name = "craft_selector"

    def run(
        self,
        request: StoryRequest,
        characters: CharactersArtifact,
        storyline: IncrementalStorylineArtifact,
        variants: CraftVariantsArtifact,
        repair_feedback: str = "",
    ) -> CraftSelectionArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Select exactly one supplied craft variant. Prefer faithful user-constraint coverage, "
                "causal fit with the accepted storyline, clear global and chapter-level progression, "
                "earned payoffs, and observable low-to-high main-character growth. Return only a valid "
                "variant ID and a concise rationale. Do not assign numeric quality scores."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nACCEPTED STORYLINE:\n{json_text(storyline)}"
                f"\n\nCRAFT VARIANTS:\n{json_text(variants)}{repair_feedback}"
            ),
            schema=CraftSelectionArtifact,
        )


class CraftCriticAgent(Agent[CraftAuditArtifact]):
    name = "craft_critic"

    def run(
        self,
        request: StoryRequest,
        variant: CraftVariant,
        characters: CharactersArtifact,
        outline: StoryOutlineArtifact,
        storyline: IncrementalStorylineArtifact,
        draft: str,
    ) -> CraftAuditArtifact:
        questions = audit_questions(request, variant, characters)
        raw = self.provider.generate_structured(
            system_instruction=(
                "You are a demanding story-craft critic. Answer every supplied question exactly once "
                "using its exact question_id, category, subject_id, question, and blocking value. Judge "
                "the fiction rather than planning labels and cite concise location-specific evidence. "
                "A failure must include an actionable issue and revision instruction. Use not_applicable "
                "only for non-blocking questions. Do not assign scores or invent questions."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nCRAFT VARIANT:\n{json_text(variant)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}\n\nOUTLINE:\n{json_text(outline)}"
                f"\n\nSTORYLINE:\n{json_text(storyline)}"
                f"\n\nQUESTIONS:\n{json.dumps(questions, ensure_ascii=False, indent=2)}"
                f"\n\nFICTION:\n{draft}"
            ),
            schema=CraftAuditArtifact,
        )
        return normalize_audit(raw, questions)


class CraftRewriterAgent(Agent[str]):
    name = "craft_rewriter"

    def run(
        self,
        request: StoryRequest,
        variant: CraftVariant,
        characters: CharactersArtifact,
        outline: StoryOutlineArtifact,
        storyline: IncrementalStorylineArtifact,
        draft: str,
        audit: CraftAuditArtifact,
        length_instruction: str = "",
    ) -> str:
        failed = [answer for answer in audit.answers if answer.verdict == "fail"]
        failed.sort(key=lambda answer: not answer.blocking)
        return self.provider.generate_text(
            system_instruction=(
                "You are a literary rewriter. Rewrite the complete fiction once, applying every failed "
                "audit instruction. Preserve accepted facts, causal dependencies, event outcomes, user "
                "constraints, requested language, and approximate length. Realize global and local "
                "promise-progress-payoff lines, character growth, and try-fail consequences through "
                "action and choice. Never expose scores, IDs, questions, or planning terminology. Return "
                "only the complete revised story in Markdown and preserve every canonical chapter heading."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nCRAFT VARIANT:\n{json_text(variant)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}\n\nOUTLINE:\n{json_text(outline)}"
                f"\n\nSTORYLINE:\n{json_text(storyline)}\n\nFAILED AUDIT ANSWERS:\n"
                f"{json.dumps([answer.model_dump(mode='json') for answer in failed], ensure_ascii=False, indent=2)}"
                f"\n\nDETERMINISTIC LENGTH INSTRUCTION:\n{length_instruction or 'none'}"
                f"\n\nDRAFT:\n{draft}"
            ),
        )
