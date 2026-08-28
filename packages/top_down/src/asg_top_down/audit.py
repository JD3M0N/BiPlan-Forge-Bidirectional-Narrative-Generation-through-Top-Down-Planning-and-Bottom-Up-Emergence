"""Word-count auditing for generated and edited stories."""

from __future__ import annotations

import math
import re

from .schemas import (
    ChapterLengthAudit,
    ChapterPlan,
    LengthAuditArtifact,
    LengthAuditEntry,
    StoryPlan,
    StoryRequest,
)


def word_count(text: str) -> int:
    """Count whitespace-delimited words in a story fragment."""
    return len(text.split())


def word_bounds(target: int) -> tuple[int, int]:
    """Return the accepted lower and upper word-count bounds."""
    return math.floor(target * 0.90), math.ceil(target * 1.20)


def canonical_chapter(title: str, body: str) -> str:
    """Render a chapter body with its canonical Markdown heading."""
    return f"## {title}\n\n{body.strip()}"


def parse_chapter_bodies(story: str, expected: int) -> list[str]:
    """Recover edited chapter bodies when every Markdown heading is preserved."""
    headings = list(re.finditer(r"(?m)^##\s+.+$", story))
    if len(headings) != expected:
        return []
    return [
        story[
            heading.end() : (headings[index + 1].start() if index + 1 < expected else None)
        ].strip()
        for index, heading in enumerate(headings)
    ]


def audit_chapter(chapter: ChapterPlan, body: str) -> ChapterLengthAudit:
    """Measure one chapter against its configured target."""
    minimum, maximum = word_bounds(chapter.target_words)
    actual = word_count(body)
    return ChapterLengthAudit(
        chapter_id=chapter.id,
        target_words=chapter.target_words,
        minimum_words=minimum,
        maximum_words=maximum,
        actual_words=actual,
        within_tolerance=minimum <= actual <= maximum,
    )


def audit_story(
    request: StoryRequest,
    plan: StoryPlan,
    story: str,
    draft_chapter_audits: list[ChapterLengthAudit],
) -> LengthAuditArtifact:
    """Build final chapter and total audits after the optional edit pass."""
    edited_bodies = parse_chapter_bodies(story, len(plan.chapters))
    chapter_audits = (
        [
            audit_chapter(chapter, body)
            for chapter, body in zip(plan.chapters, edited_bodies, strict=True)
        ]
        if edited_bodies
        else draft_chapter_audits
    )
    minimum, maximum = word_bounds(request.target_words)
    actual = word_count(story)
    return LengthAuditArtifact(
        chapters=chapter_audits,
        total=LengthAuditEntry(
            target_words=request.target_words,
            minimum_words=minimum,
            maximum_words=maximum,
            actual_words=actual,
            within_tolerance=minimum <= actual <= maximum,
        ),
    )
