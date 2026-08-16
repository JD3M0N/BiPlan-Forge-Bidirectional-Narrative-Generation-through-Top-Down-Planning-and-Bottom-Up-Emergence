"""Agents that design and enforce the production craft contract."""

from __future__ import annotations

import json

from .base import Agent, json_text
from ..craft import audit_questions, normalize_audit, try_fail_target
from ..schemas import (
    CharactersArtifact, CraftAuditArtifact, CraftContractArtifact,
    IncrementalStorylineArtifact, StoryOutlineArtifact, StoryPlanArtifact,
    StoryRequest, WorldArtifact,
)


class CraftContractAgent(Agent[CraftContractArtifact]):
    name = "craft_contract"

    def run(
        self,
        request: StoryRequest,
        plan: StoryPlanArtifact,
        world: WorldArtifact,
        characters: CharactersArtifact,
        repair_feedback: str = "",
    ) -> CraftContractArtifact:
        target = try_fail_target(request.target_words)
        return self.provider.generate_structured(
            system_instruction=(
                "Design a compact Sanderson craft contract before outlining. Create exactly one "
                "tone promise, exactly one main-plot promise, and exactly one character promise "
                "for every main character. Each promise needs a concrete setup, one or more visible "
                "progress signals, and a specific payoff. Set try_fail_target to the supplied exact "
                "value. Do not add MICE, want/need/Lie, magic laws, or prose-style rules."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nPLAN:\n{json_text(plan)}"
                f"\n\nWORLD:\n{json_text(world)}\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nEXACT TRY-FAIL TARGET: {target}{repair_feedback}"
            ),
            schema=CraftContractArtifact,
        )


class CraftCriticAgent(Agent[CraftAuditArtifact]):
    name = "craft_critic"

    def run(
        self,
        request: StoryRequest,
        contract: CraftContractArtifact,
        characters: CharactersArtifact,
        outline: StoryOutlineArtifact,
        storyline: IncrementalStorylineArtifact,
        draft: str,
    ) -> CraftAuditArtifact:
        questions = audit_questions(contract, characters, outline)
        raw = self.provider.generate_structured(
            system_instruction=(
                "You are a demanding story-craft critic. Answer every supplied question exactly "
                "once using its exact question_id, category, subject_id, question, and blocking "
                "value. Judge the fiction rather than trusting planning labels. Cite concise, "
                "location-specific evidence. A failure must include a concrete issue and an "
                "actionable revision instruction. Use not_applicable only for non-blocking questions. "
                "Do not assign numeric quality scores or invent additional questions."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nCRAFT CONTRACT:\n{json_text(contract)}"
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
        contract: CraftContractArtifact,
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
                "You are a literary rewriter. Rewrite the complete fiction once, applying every "
                "failed audit instruction. Preserve established facts, causal dependencies, event "
                "outcomes, requested language, and approximate length. Show promises, character "
                "slider movement, and try-fail consequences through action and choice. Never expose "
                "scores, IDs, audit questions, or planning terminology. Return only the complete "
                "revised story in Markdown. Preserve every canonical Markdown chapter heading "
                "exactly as supplied in the draft; never rename or duplicate a heading."
            ),
            prompt=(
                f"REQUEST:\n{json_text(request)}\n\nCRAFT CONTRACT:\n{json_text(contract)}"
                f"\n\nCHARACTERS:\n{json_text(characters)}\n\nOUTLINE:\n{json_text(outline)}"
                f"\n\nSTORYLINE:\n{json_text(storyline)}\n\nFAILED AUDIT ANSWERS:\n"
                f"{json.dumps([answer.model_dump(mode='json') for answer in failed], ensure_ascii=False, indent=2)}"
                f"\n\nDETERMINISTIC LENGTH INSTRUCTION:\n{length_instruction or 'none'}"
                f"\n\nDRAFT:\n{draft}"
            ),
        )
