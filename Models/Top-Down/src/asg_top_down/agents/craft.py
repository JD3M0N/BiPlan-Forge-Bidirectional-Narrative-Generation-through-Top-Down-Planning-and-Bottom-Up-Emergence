"""Post-STORYLINE craft planners, critic, and selective chapter rewriter."""

from __future__ import annotations

import json

from .base import Agent, json_text
from ..craft import audit_questions, normalize_audit, try_fail_target
from ..schemas import (
    CharacterArcPlan, CharactersArtifact, CraftAuditArtifact, CraftComposition,
    IncrementalStorylineArtifact, PromiseLedger, StoryCraftPlan,
    StoryOutlineArtifact, StoryPlanArtifact, StoryRequest, TaxonomyBrief, TryFailPlan,
)


class PromiseLedgerPlannerAgent(Agent[PromiseLedger]):
    name = "promise_ledger"

    def run(self, request: StoryRequest, plan: StoryPlanArtifact,
            characters: CharactersArtifact, outline: StoryOutlineArtifact,
            storyline: IncrementalStorylineArtifact,
            taxonomy_brief: TaxonomyBrief | None = None,
            repair_feedback: str = "") -> PromiseLedger:
        return self.provider.generate_structured(
            system_instruction=(
                "The factual STORYLINE is frozen. Design a global Promise-Progress-Payoff ledger over it; "
                "never request, imply, or perform event regeneration. Include exactly one story-direction, "
                "one character/conflict, and one genre/structure promise. Each has one opening, visible "
                "advance/complicate/reframe progresses, and one costly prepared payoff. The primary promise "
                "opens first and pays in the final chapter; use at least two progresses for 1200+ words. "
                "Connect the internal need to the external resolution. Use chapter IDs and English text."
            ),
            prompt=(
                f"NORMALIZED SPECIFICATION:\n{json_text(request.agent_spec())}\n\nSTORY FRAME:\n"
                f"{json_text(plan.story_frame)}\n\nCHARACTERS:\n{json_text(characters)}"
                f"\n\nOUTLINE:\n{json_text(outline)}\n\nFROZEN STORYLINE:\n{json_text(storyline)}"
                f"\n\nGENRE PALETTE:\n{json_text(taxonomy_brief) if taxonomy_brief else 'none'}"
                f"{repair_feedback}"
            ),
            schema=PromiseLedger,
        )


class CharacterArcPlannerAgent(Agent[CharacterArcPlan]):
    name = "character_arcs"

    def run(self, characters: CharactersArtifact, outline: StoryOutlineArtifact,
            storyline: IncrementalStorylineArtifact, ledger: PromiseLedger,
            repair_feedback: str = "") -> CharacterArcPlan:
        return self.provider.generate_structured(
            system_instruction=(
                "Plan exactly four behavioral evidences for every main character over the frozen "
                "STORYLINE: establishment, pressure, decisive_choice, consequence. Honor each profile's "
                "positive, negative, or flat arc direction. The flaw must impose its stated cost; the "
                "decisive choice must expose want versus need; the internal outcome must enable or prevent "
                "an external promise payoff. Fill both want/need choice fields and the explicit "
                "enables/prevents rationale. Use chapter IDs and English text, never alter events."
            ),
            prompt=(f"CHARACTERS:\n{json_text(characters)}\n\nOUTLINE:\n{json_text(outline)}"
                    f"\n\nFROZEN STORYLINE:\n{json_text(storyline)}\n\nLEDGER:\n{json_text(ledger)}"
                    f"{repair_feedback}"),
            schema=CharacterArcPlan,
        )


class TryFailPlannerAgent(Agent[TryFailPlan]):
    name = "try_fail"

    def run(self, request: StoryRequest, outline: StoryOutlineArtifact,
            storyline: IncrementalStorylineArtifact, ledger: PromiseLedger,
            repair_feedback: str = "") -> TryFailPlan:
        count = try_fail_target(request.target_words)
        return self.provider.generate_structured(
            system_instruction=(
                "Build try-fail cycles only after and over the frozen STORYLINE. Each cycle is yes_but "
                "or no_and, changes the terms of the problem, teaches something, and raises or transforms "
                "the cost. Link it to an active promise and chapter. A plain yes/no is reserved for final "
                "resolution and is not a try-fail cycle. Never alter factual events. Return English text."
            ),
            prompt=(f"NORMALIZED SPECIFICATION:\n{json_text(request.agent_spec())}"
                    f"\n\nOUTLINE:\n{json_text(outline)}\n\nFROZEN STORYLINE:\n{json_text(storyline)}"
                    f"\n\nLEDGER:\n{json_text(ledger)}\n\nEXACT CYCLE COUNT: {count}{repair_feedback}"),
            schema=TryFailPlan,
        )


class CraftComposerAgent(Agent[CraftComposition]):
    name = "craft_alignment"

    def run(self, outline: StoryOutlineArtifact, storyline: IncrementalStorylineArtifact,
            ledger: PromiseLedger, arcs: CharacterArcPlan, try_fail: TryFailPlan,
            repair_feedback: str = "") -> CraftComposition:
        return self.provider.generate_structured(
            system_instruction=(
                "Align every promise beat, character evidence, and try-fail cycle to one or more accepted "
                "node IDs in its own chapter. Cover every craft ID exactly once. Then derive one chapter "
                "craft view per chapter, listing only promises opened, progressed, or paid there. A chapter "
                "may have empty phases but must act on an active promise. Add scene directives separately: "
                "goal, conflict, yes_but/no_and or CEN-only final_resolution, consequence, reaction, dilemma, "
                "decision. Repair craft alignment only; the STORYLINE is immutable. Return English text."
            ),
            prompt=(f"OUTLINE:\n{json_text(outline)}\n\nFROZEN STORYLINE:\n{json_text(storyline)}"
                    f"\n\nLEDGER:\n{json_text(ledger)}\n\nARCS:\n{json_text(arcs)}"
                    f"\n\nTRY-FAIL:\n{json_text(try_fail)}{repair_feedback}"),
            schema=CraftComposition,
        )


class CraftCriticAgent(Agent[CraftAuditArtifact]):
    name = "craft_critic"

    def run(self, request: StoryRequest, craft: StoryCraftPlan,
            characters: CharactersArtifact, outline: StoryOutlineArtifact,
            storyline: IncrementalStorylineArtifact, draft: str,
            taxonomy_brief: TaxonomyBrief | None = None) -> CraftAuditArtifact:
        questions = audit_questions(request, craft, characters, taxonomy_brief)
        raw = self.provider.generate_structured(
            system_instruction=(
                "Answer every supplied story-craft question exactly once. Identify affected chapter IDs "
                "for every localizable failure. Coherence includes world state, knowledge, causality, and "
                "motivation; pacing requires visible progress; engagement and satisfaction require prepared "
                "and fulfilled promises. Cite evidence, assign no scores, and make failures actionable."
            ),
            prompt=(f"NORMALIZED SPECIFICATION:\n{json_text(request.agent_spec())}"
                    f"\n\nCRAFT:\n{json_text(craft)}\n\nCHARACTERS:\n{json_text(characters)}"
                    f"\n\nOUTLINE:\n{json_text(outline)}\n\nFROZEN STORYLINE:\n{json_text(storyline)}"
                    f"\n\nQUESTIONS:\n{json.dumps(questions, ensure_ascii=False, indent=2)}"
                    f"\n\nFICTION:\n{draft}"),
            schema=CraftAuditArtifact,
        )
        return normalize_audit(raw, questions)


class ChapterRewriterAgent(Agent[str]):
    name = "chapter_rewriter"

    def run(self, request: StoryRequest, chapter_id: str, chapter_title: str,
            chapter_text: str, chapter_context: dict, audit_answers: list,
            length_instruction: str = "") -> str:
        return self.provider.generate_text(
            system_instruction=(
                f"Rewrite only this fiction chapter body in {request.language}. Preserve all accepted "
                "facts, event order, causal outcomes, proper nouns, and the chapter title (which you must "
                "not output). Apply only supplied repair instructions. Do not expose IDs or planning terms."
            ),
            prompt=(f"NORMALIZED SPECIFICATION:\n{json_text(request.agent_spec())}"
                    f"\n\nCHAPTER CONTEXT:\n{json_text(chapter_context)}"
                    f"\n\nFAILED CHECKS:\n{json_text(audit_answers)}"
                    f"\n\nLENGTH:\n{length_instruction or 'Preserve approximate length.'}"
                    f"\n\nCHAPTER BODY:\n{chapter_text}"),
        )
