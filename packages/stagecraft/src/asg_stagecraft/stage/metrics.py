"""Observed characteristics of one performance, and of the prose narrated from it.

Every figure here is an observation, never a target: nothing in this module reaches a prompt,
and there is a test that says so. They exist to answer the questions the thesis actually asks -
did the beats land or were they forced, did the actors improvise or echo the script, did anyone
speak about something they never learned, and what did it all cost.

Two are worth naming. ``script_echo`` measures how closely a performed line resembles the
scripted line it replaced, so a value near 1 means the actors recited and the simulation added
nothing. ``unknown_mentions`` counts a speaker naming a character absent from its own memory: a
cheap, deterministic proxy for a knowledge-boundary leak, which the optional LLM audit then
measures properly.

Two more were misread once and are documented so they are not misread again.
``repetition_ratio`` compares speech word for word, so it is blind to paraphrase and to
gestures; ``action_repetition_ratio`` covers the gestures. ``dialogue_survival`` near 1 is not
fidelity: it means the narrator transcribed the log instead of curating it, which
``compression_ratio`` above 1 confirms.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from ..formats import ActorMemory, NarrativeVoice
from ..planning.profiles import NarrativeProfile
from ..schemas import ID_PATTERN
from .casting import gates_known_by_discoverer
from .memory import CharacterMemory
from .schemas import (
    YIELDING_TACTICS,
    CastBible,
    PerformanceArtifact,
    ScenePerformance,
    StageTurn,
)
from .validation import (
    ACTION_CONTAINMENT,
    MAX_SPEECH_WORDS,
    REPETITION_THRESHOLD,
    containment,
    echo_of,
    is_first_person_action,
    similarity,
)


class ActorMetrics(BaseModel):
    """What one character did across the whole performance."""

    character_id: str = Field(pattern=ID_PATTERN)
    scenes: int = Field(default=0, ge=0)
    turns: int = Field(default=0, ge=0)
    speech_words: int = Field(default=0, ge=0)
    action_words: int = Field(default=0, ge=0)
    thought_words: int = Field(default=0, ge=0)
    whispers: int = Field(default=0, ge=0)
    unprompted_turns: int = Field(default=0, ge=0)
    distinct_tactics: int = Field(default=0, ge=0)
    repaired_turns: int = Field(default=0, ge=0)
    memory_records: int = Field(default=0, ge=0)
    retrievals: int = Field(default=0, ge=0)
    max_self_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    emotions: list[str] = Field(default_factory=list)


class SceneMetrics(BaseModel):
    """What one scene produced, beat by beat."""

    scene_id: str = Field(pattern=ID_PATTERN)
    chapter_id: str = Field(pattern=ID_PATTERN)
    turns: int = Field(default=0, ge=0)
    beats: int = Field(default=0, ge=0)
    beats_achieved: int = Field(default=0, ge=0)
    beats_forced: int = Field(default=0, ge=0)
    beats_intervened: int = Field(default=0, ge=0)
    checks: int = Field(default=0, ge=0)
    stage_events: int = Field(default=0, ge=0)
    reaction_turns: int = Field(default=0, ge=0)
    coda_turns: int = Field(default=0, ge=0)
    rejected_turns: int = Field(default=0, ge=0)
    skipped_turns: int = Field(default=0, ge=0)
    script_echo: float = Field(default=0.0, ge=0.0, le=1.0)


class SimulationMetrics(BaseModel):
    """Record observed performance and narration characteristics, never a budget."""

    narrative_profile: NarrativeProfile
    narrative_voice: NarrativeVoice
    actor_memory: ActorMemory
    scenes: int = Field(default=0, ge=0)
    turns: int = Field(default=0, ge=0)
    beats: int = Field(default=0, ge=0)
    beats_achieved: int = Field(default=0, ge=0)
    beats_forced: int = Field(default=0, ge=0)
    # Reached only after the world stepped in. Counted inside beats_achieved as well.
    beats_intervened: int = Field(default=0, ge=0)
    beat_completion_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    turns_per_beat: float = Field(default=0.0, ge=0.0)
    director_checks: int = Field(default=0, ge=0)
    stage_events: int = Field(default=0, ge=0)
    reaction_turns: int = Field(default=0, ge=0)
    coda_turns: int = Field(default=0, ge=0)
    rejected_turns: int = Field(default=0, ge=0)
    skipped_turns: int = Field(default=0, ge=0)
    speech_words: int = Field(default=0, ge=0)
    action_words: int = Field(default=0, ge=0)
    thought_words: int = Field(default=0, ge=0)
    whispers: int = Field(default=0, ge=0)
    repetition_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    action_repetition_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    first_person_actions: int = Field(default=0, ge=0)
    thought_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    long_speeches: int = Field(default=0, ge=0)
    yields: int = Field(default=0, ge=0)
    max_tactic_streak: int = Field(default=0, ge=0)
    gates_known_by_discoverer: int = Field(default=0, ge=0)
    mean_self_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    script_echo: float = Field(default=0.0, ge=0.0, le=1.0)
    unknown_mentions: int = Field(default=0, ge=0)
    memory_records: int = Field(default=0, ge=0)
    retrievals: int = Field(default=0, ge=0)
    narration_source_fallbacks: int = Field(default=0, ge=0)
    narrated_words: int = Field(default=0, ge=0)
    log_words: int = Field(default=0, ge=0)
    compression_ratio: float = Field(default=0.0, ge=0.0)
    dialogue_survival: float = Field(default=0.0, ge=0.0, le=1.0)
    scene_metrics: list[SceneMetrics] = Field(default_factory=list)
    actor_metrics: list[ActorMetrics] = Field(default_factory=list)


def simulation_metrics(
    *,
    profile: NarrativeProfile,
    performance: PerformanceArtifact,
    scripted_by_scene: dict[str, list[str]],
    memories: dict[str, CharacterMemory],
    names: dict[str, str],
    story: str,
    narration_fallbacks: int,
    bible: CastBible | None = None,
) -> SimulationMetrics:
    """Measure one finished performance and the prose narrated from it."""
    scenes = performance.scenes
    all_turns = [turn for scene in scenes for turn in scene.turns]
    acted = [turn for turn in all_turns if turn.kind == "actor"]
    actions = [turn.action for turn in acted if turn.action]
    log_words = sum(
        len(turn.speech.split()) + len(turn.action.split()) + len(turn.thought.split())
        for turn in all_turns
    )
    narrated_words = len(story.split())
    scene_metrics = [
        _scene_metrics(scene, scripted_by_scene.get(scene.scene_id, [])) for scene in scenes
    ]
    actor_metrics = _actor_metrics(scenes, memories)

    beats = sum(len(scene.beats) for scene in scenes)
    achieved = sum(1 for scene in scenes for beat in scene.beats if beat.achieved)
    forced = sum(1 for scene in scenes for beat in scene.beats if beat.forced)
    intervened = sum(1 for scene in scenes for beat in scene.beats if beat.intervened)
    similarities = [item.max_self_similarity for item in actor_metrics if item.turns > 1]
    echoes = [item.script_echo for item in scene_metrics if item.script_echo > 0]

    return SimulationMetrics(
        narrative_profile=profile,
        narrative_voice=NarrativeVoice.OMNISCIENT,
        actor_memory=performance.settings.actor_memory,
        scenes=len(scenes),
        turns=len(all_turns),
        beats=beats,
        beats_achieved=achieved,
        beats_forced=forced,
        beats_intervened=intervened,
        beat_completion_ratio=round(achieved / beats, 4) if beats else 0.0,
        turns_per_beat=round(len(all_turns) / beats, 2) if beats else 0.0,
        director_checks=sum(item.checks for item in scene_metrics),
        stage_events=sum(item.stage_events for item in scene_metrics),
        reaction_turns=sum(item.reaction_turns for item in scene_metrics),
        coda_turns=sum(item.coda_turns for item in scene_metrics),
        rejected_turns=sum(scene.rejected for scene in scenes),
        skipped_turns=sum(scene.skipped for scene in scenes),
        speech_words=sum(item.speech_words for item in actor_metrics),
        action_words=sum(item.action_words for item in actor_metrics),
        thought_words=sum(item.thought_words for item in actor_metrics),
        whispers=sum(item.whispers for item in actor_metrics),
        repetition_ratio=round(_repetition_ratio(scenes), 4),
        action_repetition_ratio=round(_action_repetition_ratio(acted), 4),
        first_person_actions=sum(1 for action in actions if is_first_person_action(action)),
        thought_ratio=round(sum(1 for turn in acted if turn.thought) / len(acted), 4)
        if acted
        else 0.0,
        long_speeches=sum(1 for turn in acted if len(turn.speech.split()) > MAX_SPEECH_WORDS),
        yields=sum(1 for turn in acted if turn.tactic in YIELDING_TACTICS),
        max_tactic_streak=_max_tactic_streak(scenes),
        gates_known_by_discoverer=gates_known_by_discoverer(bible) if bible else 0,
        mean_self_similarity=round(sum(similarities) / len(similarities), 4)
        if similarities
        else 0.0,
        script_echo=round(sum(echoes) / len(echoes), 4) if echoes else 0.0,
        unknown_mentions=_unknown_mentions(acted, memories, names),
        memory_records=sum(item.memory_records for item in actor_metrics),
        retrievals=sum(item.retrievals for item in actor_metrics),
        narration_source_fallbacks=narration_fallbacks,
        narrated_words=narrated_words,
        log_words=log_words,
        compression_ratio=round(narrated_words / log_words, 4) if log_words else 0.0,
        dialogue_survival=round(_dialogue_survival(all_turns, story), 4),
        scene_metrics=scene_metrics,
        actor_metrics=actor_metrics,
    )


def _scene_metrics(scene: ScenePerformance, scripted: list[str]) -> SceneMetrics:
    """Summarize one scene's beats and how far its lines drifted from the script."""
    spoken = [turn.speech for turn in scene.turns if turn.speech]
    echoes = [echo_of(line, scripted) for line in spoken] if scripted else []
    return SceneMetrics(
        scene_id=scene.scene_id,
        chapter_id=scene.chapter_id,
        turns=len(scene.turns),
        beats=len(scene.beats),
        beats_achieved=sum(1 for beat in scene.beats if beat.achieved),
        beats_forced=sum(1 for beat in scene.beats if beat.forced),
        beats_intervened=sum(1 for beat in scene.beats if beat.intervened),
        checks=sum(beat.checks for beat in scene.beats),
        stage_events=sum(len(beat.stage_events) for beat in scene.beats),
        reaction_turns=sum(beat.reaction_turns for beat in scene.beats),
        coda_turns=scene.coda_turns,
        rejected_turns=scene.rejected,
        skipped_turns=scene.skipped,
        script_echo=round(sum(echoes) / len(echoes), 4) if echoes else 0.0,
    )


def _actor_metrics(
    scenes: list[ScenePerformance], memories: dict[str, CharacterMemory]
) -> list[ActorMetrics]:
    """Tally what each character contributed, in stable character order."""
    tallies: dict[str, ActorMetrics] = {}
    scene_presence: dict[str, set[str]] = {}
    spoken: dict[str, list[str]] = {}
    tactics: dict[str, set[str]] = {}
    for scene in scenes:
        for turn in scene.turns:
            if turn.kind == "world":
                continue
            item = tallies.setdefault(turn.actor_id, ActorMetrics(character_id=turn.actor_id))
            item.turns += 1
            item.speech_words += len(turn.speech.split())
            item.action_words += len(turn.action.split())
            item.thought_words += len(turn.thought.split())
            item.whispers += int(turn.visibility == "whisper")
            item.unprompted_turns += int(not turn.direction_note)
            item.repaired_turns += int(turn.attempts > 1)
            scene_presence.setdefault(turn.actor_id, set()).add(turn.scene_id)
            if turn.speech:
                spoken.setdefault(turn.actor_id, []).append(turn.speech)
            if turn.tactic:
                tactics.setdefault(turn.actor_id, set()).add(turn.tactic.casefold())
    for character_id, item in tallies.items():
        item.scenes = len(scene_presence.get(character_id, ()))
        item.distinct_tactics = len(tactics.get(character_id, ()))
        lines = spoken.get(character_id, [])
        item.max_self_similarity = round(_peak_self_similarity(lines), 4)
        memory = memories.get(character_id)
        if memory is not None:
            item.memory_records = len(memory.records)
            item.retrievals = len(memory.retrievals)
    return [tallies[key] for key in sorted(tallies)]


def _peak_self_similarity(lines: list[str]) -> float:
    """Return the highest overlap any line has with an earlier line by the same speaker."""
    peak = 0.0
    for index, line in enumerate(lines):
        for earlier in lines[:index]:
            peak = max(peak, similarity(line, earlier))
    return peak


def _repetition_ratio(scenes: list[ScenePerformance]) -> float:
    """Return what fraction of spoken turns repeat something that speaker already said."""
    spoken: dict[str, list[str]] = {}
    repeats = total = 0
    for scene in scenes:
        for turn in scene.turns:
            if not turn.speech or turn.kind == "world":
                continue
            total += 1
            earlier = spoken.setdefault(turn.actor_id, [])
            if any(similarity(turn.speech, item) >= REPETITION_THRESHOLD for item in earlier):
                repeats += 1
            earlier.append(turn.speech)
    return repeats / total if total else 0.0


def _action_repetition_ratio(turns: list[StageTurn]) -> float:
    """Return what fraction of actions replay a gesture the same actor already made.

    Measured against every earlier action of the actor, not only the validator's recent window,
    so a tic that comes back after a pause still counts. Containment rather than overlap, as in
    the validator: the real repeats kept the whole gesture and added a clause.
    """
    earlier: dict[str, list[str]] = {}
    repeats = total = 0
    for turn in turns:
        if not turn.action:
            continue
        total += 1
        previous = earlier.setdefault(turn.actor_id, [])
        if any(containment(item, turn.action) >= ACTION_CONTAINMENT for item in previous):
            repeats += 1
        previous.append(turn.action)
    return repeats / total if total else 0.0


def _max_tactic_streak(scenes: list[ScenePerformance]) -> int:
    """Return the longest run of one actor repeating the same tactic within a scene.

    The standoff indicator: "confront, confront, confront" is a table nobody is crossing.
    """
    longest = 0
    for scene in scenes:
        last: dict[str, tuple[str, int]] = {}
        for turn in scene.turns:
            if turn.kind == "world" or not turn.tactic:
                continue
            tactic, run = last.get(turn.actor_id, ("", 0))
            run = run + 1 if turn.tactic == tactic else 1
            last[turn.actor_id] = (turn.tactic, run)
            longest = max(longest, run)
    return longest


def _unknown_mentions(
    turns: list[StageTurn],
    memories: dict[str, CharacterMemory],
    names: dict[str, str],
) -> int:
    """Count turns naming a character the speaker has no memory of, as a leak proxy."""
    leaks = 0
    seen: dict[str, set[str]] = {}
    for turn in turns:
        known = seen.setdefault(turn.actor_id, set())
        memory = memories.get(turn.actor_id)
        if memory is not None:
            for record in memory.records:
                known.update(record.participants)
        text = f"{turn.speech} {turn.action}".casefold()
        for other, name in names.items():
            if other == turn.actor_id or other in known or not name:
                continue
            if name.casefold() in text:
                leaks += 1
    return leaks


def _dialogue_survival(turns: list[StageTurn], story: str) -> float:
    """Return what fraction of performed lines left a recognizable trace in the prose."""
    spoken = [turn.speech for turn in turns if turn.speech]
    if not spoken or not story:
        return 0.0
    words = Counter(story.casefold().split())
    survived = 0
    for line in spoken:
        tokens = [token for token in line.casefold().split() if len(token) > 3]
        if not tokens:
            continue
        hits = sum(1 for token in tokens if words[token])
        if hits / len(tokens) >= 0.5:
            survived += 1
    return survived / len(spoken)
