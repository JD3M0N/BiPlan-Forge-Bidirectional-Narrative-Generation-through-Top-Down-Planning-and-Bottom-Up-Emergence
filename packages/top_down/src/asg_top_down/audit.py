"""Observed metrics for generated stories."""

from __future__ import annotations

import re

from .schemas import ChapterMetrics, StoryMetrics, StoryPlan, StoryRequest


def word_count(text: str) -> int:
    """Count whitespace-delimited words in a story fragment."""
    return len(text.split())


def canonical_chapter(title: str, body: str) -> str:
    """Render a chapter body with its canonical Markdown heading."""
    return f"## {title}\n\n{body.strip()}"


def parse_chapter_bodies(story: str, expected: int) -> list[str]:
    """Recover final chapter bodies when every canonical heading is preserved."""
    headings = list(re.finditer(r"(?m)^##\s+.+$", story))
    if len(headings) != expected:
        return []
    return [
        story[
            heading.end() : (headings[index + 1].start() if index + 1 < expected else None)
        ].strip()
        for index, heading in enumerate(headings)
    ]


def story_metrics(request: StoryRequest, plan: StoryPlan, story: str) -> StoryMetrics:
    """Build non-prescriptive metrics from the completed story and graph."""
    bodies = parse_chapter_bodies(story, len(plan.chapters))
    if not bodies:
        bodies = [""] * len(plan.chapters)
    event_counts = {chapter.id: 0 for chapter in plan.chapters}
    for event in plan.events:
        event_counts[event.chapter_id] += 1
    return StoryMetrics(
        narrative_profile=request.narrative_profile,
        words=word_count(story),
        chapters=len(plan.chapters),
        events=len(plan.events),
        chapter_metrics=[
            ChapterMetrics(
                chapter_id=chapter.id,
                words=word_count(body),
                events=event_counts[chapter.id],
            )
            for chapter, body in zip(plan.chapters, bodies, strict=True)
        ],
    )
