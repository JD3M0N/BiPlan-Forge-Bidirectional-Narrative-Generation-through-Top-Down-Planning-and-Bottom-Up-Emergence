"""Deterministic assembly of the final Markdown document.

Ordering is never delegated to a model: the chapters follow the validated plan and the
headings come from the localized presentation, so two runs of the same plan assemble the
same document.
"""

from __future__ import annotations

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
