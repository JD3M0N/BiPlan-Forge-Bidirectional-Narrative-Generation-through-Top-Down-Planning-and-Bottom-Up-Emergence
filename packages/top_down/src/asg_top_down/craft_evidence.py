"""Qualitative prose-craft evidence handed to the Drama Critic."""

from __future__ import annotations

from asg_core import craft_metrics

from .schemas import ChapterCraftEvidence, ChapterPlan, CraftEvidenceArtifact

# Recalibrated on the 90 chapters of the 23 finished 6.6.0 runs, read from the per-chapter figures
# story_metrics.json has carried since 6.5.0. A safety net belongs just outside the healthy
# distribution, not at one of its quartiles: a quartile fires on a quarter of healthy chapters and
# stops meaning anything. The dialogue floor is left where it was, because 0.20 still sits on the
# real tail -- it caught 1 chapter of 90, the lowest observed being 0.1765. The paragraph ceiling
# moved, because 6.6.0 tops out at 64.6 words per paragraph (p99 55.9) and 120 had become
# unreachable: the pre-intervention 6.5.0 corpus reached 217. The figures stay here, in code, and
# only their verdict travels: profiles.py records why a number written inside a prompt beats every
# other.
LOW_DIALOGUE_RATIO = 0.20
BLOCK_PARAGRAPH_WORDS = 90.0

NO_DIALOGUE = "no spoken exchange appears anywhere in this chapter"
RARE_DIALOGUE = "spoken exchange is rare, so the chapter is reported rather than played out"
BLOCK_PARAGRAPHS = "paragraphs run as undivided blocks instead of breaking at each beat"

EVIDENCE_PREFACE = (
    "Observed deterministically in the draft below, not requested by the user. Every line names a "
    "chapter whose prose reads as narration about events instead of scene. Chapters that read as "
    "scene are omitted. Treat this as evidence for your own notes, never as a target to hit."
)


def chapter_observations(body: str) -> list[str]:
    """List the craft deficits one drafted chapter body shows."""
    craft = craft_metrics(body)
    if not craft.paragraphs:
        return []
    observations = []
    if craft.dialogue_paragraphs == 0:
        observations.append(NO_DIALOGUE)
    elif craft.dialogue_ratio < LOW_DIALOGUE_RATIO:
        observations.append(RARE_DIALOGUE)
    if craft.words_per_paragraph >= BLOCK_PARAGRAPH_WORDS:
        observations.append(BLOCK_PARAGRAPHS)
    return observations


def craft_evidence(chapters: list[ChapterPlan], bodies: list[str]) -> CraftEvidenceArtifact:
    """Audit which drafted chapters read as summary and render the critic's evidence block."""
    observed = [
        ChapterCraftEvidence(chapter_id=chapter.id, observations=chapter_observations(body))
        for chapter, body in zip(chapters, bodies, strict=True)
    ]
    lines = [
        f"- {item.chapter_id}: {'; '.join(item.observations)}."
        for item in observed
        if item.observations
    ]
    block = "\n".join([EVIDENCE_PREFACE, *lines]) if lines else ""
    return CraftEvidenceArtifact(chapters=observed, prompt_block=block)
