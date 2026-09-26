"""Observed metrics for generated stories."""

from __future__ import annotations

import re

from asg_core import craft_metrics

from ..schemas import (
    ActMetrics,
    ChapterMetrics,
    ChapterPlan,
    CharacterStageMetrics,
    PlayScript,
    ScriptMetrics,
    StoryMetrics,
    StoryPlan,
    StoryRequest,
)


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


def _chapter_metrics(chapter: ChapterPlan, body: str, events: int) -> ChapterMetrics:
    """Combine the graph event count with the prose craft of one chapter body."""
    craft = craft_metrics(body)
    return ChapterMetrics(
        chapter_id=chapter.id,
        words=word_count(body),
        events=events,
        paragraphs=craft.paragraphs,
        sentences=craft.sentences,
        dialogue_paragraphs=craft.dialogue_paragraphs,
        dialogue_ratio=craft.dialogue_ratio,
        words_per_sentence=craft.words_per_sentence,
        words_per_paragraph=craft.words_per_paragraph,
    )


def story_metrics(request: StoryRequest, plan: StoryPlan, story: str) -> StoryMetrics:
    """Build non-prescriptive metrics from the completed story and graph."""
    bodies = parse_chapter_bodies(story, len(plan.chapters))
    recovered = bool(bodies) or not plan.chapters
    if not bodies:
        bodies = [""] * len(plan.chapters)
    event_counts = {chapter.id: 0 for chapter in plan.chapters}
    for event in plan.events:
        event_counts[event.chapter_id] += 1
    craft = craft_metrics(story)
    return StoryMetrics(
        narrative_profile=request.narrative_profile,
        words=word_count(story),
        chapters=len(plan.chapters),
        events=len(plan.events),
        prose_paragraphs=craft.paragraphs,
        prose_sentences=craft.sentences,
        prose_words=craft.words,
        dash_paragraphs=craft.dash_paragraphs,
        quoted_paragraphs=craft.quoted_paragraphs,
        dialogue_paragraphs=craft.dialogue_paragraphs,
        dialogue_ratio=craft.dialogue_ratio,
        words_per_sentence=craft.words_per_sentence,
        words_per_paragraph=craft.words_per_paragraph,
        chapter_bodies_recovered=recovered,
        chapter_metrics=[
            _chapter_metrics(chapter, body, event_counts[chapter.id])
            for chapter, body in zip(plan.chapters, bodies, strict=True)
        ],
    )


def _act_metrics(act) -> ActMetrics:
    """Summarize one act's staging without judging its craft."""
    lines = [line for scene in act.scenes for line in scene.lines]
    dialogue = [line for line in lines if line.kind == "dialogue"]
    direction = [line for line in lines if line.kind == "direction"]
    events = {event_id for scene in act.scenes for event_id in scene.event_ids}
    words = sum(word_count(line.text) for line in lines) + sum(
        word_count(scene.setting) for scene in act.scenes
    )
    return ActMetrics(
        chapter_id=act.chapter_id,
        scenes=len(act.scenes),
        events=len(events),
        lines=len(lines),
        dialogue_lines=len(dialogue),
        direction_lines=len(direction),
        words=words,
    )


def _character_stage_metrics(play: PlayScript) -> list[CharacterStageMetrics]:
    """Tally stage time per character across the whole play, in cast order."""
    tallies = {member.character_id: [0, 0, 0, 0] for member in play.cast}
    for act in play.acts:
        for scene in act.scenes:
            on_stage = {member.character_id for member in scene.cast}
            for character_id in on_stage:
                if character_id in tallies:
                    tallies[character_id][0] += 1
            for line in scene.lines:
                if line.kind == "dialogue" and line.speaker_id in tallies:
                    tallies[line.speaker_id][1] += 1
                    tallies[line.speaker_id][2] += word_count(line.text)
                elif line.kind == "direction":
                    for actor_id in line.actor_ids:
                        if actor_id in tallies:
                            tallies[actor_id][3] += 1
    return [
        CharacterStageMetrics(
            character_id=character_id,
            scenes=scenes,
            lines=lines,
            words=words,
            actions=actions,
        )
        for character_id, (scenes, lines, words, actions) in tallies.items()
    ]


def _staged_cast_by_event(play: PlayScript) -> dict[str, set[str]]:
    """Map every staged event ID to the cast of every scene that stages it."""
    staged: dict[str, set[str]] = {}
    for act in play.acts:
        for scene in act.scenes:
            cast_ids = {member.character_id for member in scene.cast}
            for event_id in scene.event_ids:
                staged.setdefault(event_id, set()).update(cast_ids)
    return staged


def script_metrics(
    request: StoryRequest,
    plan: StoryPlan,
    play: PlayScript,
    rendered: str,
) -> ScriptMetrics:
    """Build non-prescriptive metrics from a completed theater script.

    Every figure here is an observation for comparing native against adapted scripts; none of
    them ever reaches a prompt.
    """
    lines = [line for act in play.acts for scene in act.scenes for line in scene.lines]
    dialogue = [line for line in lines if line.kind == "dialogue"]
    direction = [line for line in lines if line.kind == "direction"]
    dialogue_words = sum(word_count(line.text) for line in dialogue)
    direction_words = sum(word_count(line.text) for line in direction) + sum(
        word_count(scene.setting) for act in play.acts for scene in act.scenes
    )
    denominator = dialogue_words + direction_words
    staged_cast = _staged_cast_by_event(play)
    absent_participants = sum(
        len(set(event.character_ids) - staged_cast.get(event.id, set())) for event in plan.events
    )
    idle_cast = sum(
        len(
            {member.character_id for member in scene.cast}
            - {line.speaker_id for line in scene.lines if line.kind == "dialogue"}
            - {
                actor
                for line in scene.lines
                if line.kind == "direction"
                for actor in line.actor_ids
            }
        )
        for act in play.acts
        for scene in act.scenes
    )
    return ScriptMetrics(
        narrative_profile=request.narrative_profile,
        script_method=play.script_method,
        words=word_count(rendered),
        acts=len(play.acts),
        scenes=sum(len(act.scenes) for act in play.acts),
        events=len(plan.events),
        lines=len(lines),
        dialogue_lines=len(dialogue),
        direction_lines=len(direction),
        dialogue_words=dialogue_words,
        direction_words=direction_words,
        setting_words=sum(word_count(scene.setting) for act in play.acts for scene in act.scenes),
        dialogue_word_ratio=round(dialogue_words / denominator, 4) if denominator else 0.0,
        words_per_dialogue_line=round(dialogue_words / len(dialogue), 2) if dialogue else 0.0,
        words_per_direction=round(direction_words / len(direction), 2) if direction else 0.0,
        idle_cast=idle_cast,
        absent_participants=absent_participants,
        act_metrics=[_act_metrics(act) for act in play.acts],
        character_metrics=_character_stage_metrics(play),
    )
