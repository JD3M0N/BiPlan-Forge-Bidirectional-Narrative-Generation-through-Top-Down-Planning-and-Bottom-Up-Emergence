"""Deterministic assembly of the final Markdown document.

Ordering is never delegated to a model: the chapters follow the validated plan and the
headings come from the localized presentation, so two runs of the same plan assemble the
same document.
"""

from __future__ import annotations

from collections.abc import Collection

from ..schemas import StoryPlan, StoryPresentation
from .audit import canonical_chapter


def assemble_story(
    plan: StoryPlan,
    presentation: StoryPresentation,
    bodies: list[str],
) -> str:
    """Assemble canonical Markdown without delegating ordering to an LLM."""
    titles = {chapter.chapter_id: chapter.title for chapter in presentation.chapters}
    return f"# {presentation.title}\n\n" + "\n\n".join(
        canonical_chapter(titles[chapter.id], body)
        for chapter, body in zip(plan.chapters, bodies, strict=True)
    )


def narrated_plan(plan: StoryPlan, chapter_ids: Collection[str]) -> StoryPlan:
    """Return the plan cut down to the chapters a story actually tells, events included.

    A simulated story told from one character leaves out the chapters that character never
    witnessed. Both the assembly and story_metrics walk the plan against the story's bodies, so
    they must see the same cut: story_metrics also counts events per chapter, and an event whose
    chapter was dropped would have nowhere to be counted.
    """
    kept = set(chapter_ids)
    return plan.model_copy(
        update={
            "chapters": [chapter for chapter in plan.chapters if chapter.id in kept],
            "events": [event for event in plan.events if event.chapter_id in kept],
        }
    )
