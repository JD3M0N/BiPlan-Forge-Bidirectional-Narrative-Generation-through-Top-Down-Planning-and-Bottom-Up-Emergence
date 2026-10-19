"""Qualitative prose-craft evidence handed to the Drama Critic."""

from __future__ import annotations

from asg_core import craft_metrics, readability_signals

from ..schemas import (
    ChapterCraftEvidence,
    ChapterPlan,
    CharacterProfile,
    CharactersArtifact,
    CraftEvidenceArtifact,
    RevisionNote,
    WorldArtifact,
)

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
# Readability (7.12), set on the corpus the same way: just outside the 6.x chapters (p90 of 0.20
# for repeated names, 0.375 for tagged lines, 0.23 for similes), well inside what the readers of
# the 7.10 runs rejected (0.5 to 0.8 repeated names in the fallback, 0.4 to 0.6 tagged lines).
REPEATED_NAME_RATIO = 0.20
TAGGED_DIALOGUE_RATIO = 0.30
SIMILES_PER_100_WORDS = 0.25

NO_DIALOGUE = "no spoken exchange appears anywhere in this chapter"
RARE_DIALOGUE = "spoken exchange is rare, so the chapter is reported rather than played out"
BLOCK_PARAGRAPHS = "paragraphs run as undivided blocks instead of breaking at each beat"
REPEATED_NAMES = (
    "characters are named again in consecutive sentences instead of letting the verb or a "
    "pronoun carry the subject"
)
EMOTION_TAGS = "dialogue lines are followed by tags that explain the emotion instead of showing it"
SIMILE_CHAINS = "comparisons pile up, so the prose reads as ornament instead of story"
# What the critic is shown: whether a chapter plays as scene. Readability goes to the Writer as a
# note of its own, so the critic's prompt did not change when it was added.
SCENE_OBSERVATIONS = frozenset({NO_DIALOGUE, RARE_DIALOGUE, BLOCK_PARAGRAPHS})
# The id of a measured note starts with this; the Writer's acceptance judges it by the text.
CRAFT_NOTE_PREFIX = "craft_"
# Titles, and since 7.17 the articles too: "Los Sobrinos" was counted as a character named "Los".
_TITLES = frozenset(
    "lord lady sir don dona doña doctor doctora dr. dra. capitan capitana capitán custodio "
    "el la los las".split()
)

EVIDENCE_PREFACE = (
    "Observed deterministically in the draft below, not requested by the user. Every line names a "
    "chapter whose prose reads as narration about events instead of scene. Chapters that read as "
    "scene are omitted. Treat this as evidence for your own notes, never as a target to hit."
)


def chapter_observations(body: str, names: list[str] | tuple[str, ...] = ()) -> list[str]:
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
    signals = readability_signals(body, names)
    if signals.name_repeat_ratio >= REPEATED_NAME_RATIO:
        observations.append(REPEATED_NAMES)
    if signals.tagged_dialogue_ratio >= TAGGED_DIALOGUE_RATIO:
        observations.append(EMOTION_TAGS)
    if signals.similes_per_100_words >= SIMILES_PER_100_WORDS:
        observations.append(SIMILE_CHAINS)
    return observations


def character_names(characters: list[CharacterProfile]) -> list[str]:
    """The word the prose most often uses for each character: the first name, past any title."""
    names = []
    for character in characters:
        words = [word for word in character.name.split() if word.lower() not in _TITLES]
        if words:
            names.append(words[0])
    return names


def known_names(characters: CharactersArtifact, world: WorldArtifact | None = None) -> set[str]:
    """Every word of a name the story may use: the cast's, its places' and its objects' (7.17).

    An edit that brings in a capitalized word outside this set and the paragraph it rewrites
    has invented someone, and the line editor turns it down.
    """
    names = [character.name for character in characters.characters]
    if world is not None:
        names.extend(location.name for location in world.locations)
        names.extend(item.name for item in world.objects)
    return {word for name in names for word in name.split()}


def craft_evidence(
    chapters: list[ChapterPlan], bodies: list[str], names: list[str] | tuple[str, ...] = ()
) -> CraftEvidenceArtifact:
    """Audit which drafted chapters read as summary and render the critic's evidence block."""
    observed = [
        ChapterCraftEvidence(chapter_id=chapter.id, observations=chapter_observations(body, names))
        for chapter, body in zip(chapters, bodies, strict=True)
    ]
    lines = [
        f"- {item.chapter_id}: {'; '.join(scene)}."
        for item in observed
        if (scene := [line for line in item.observations if line in SCENE_OBSERVATIONS])
    ]
    block = "\n".join([EVIDENCE_PREFACE, *lines]) if lines else ""
    return CraftEvidenceArtifact(chapters=observed, prompt_block=block)


def craft_notes(evidence: CraftEvidenceArtifact) -> list[RevisionNote]:
    """Turn every observed deficit into a note the Writer receives, whatever the critic said.

    In two 7.10 runs the critic returned no note at all, so every chapter shipped as its first
    draft; an observation measured on the text is not the critic's to waive.
    """
    return [
        RevisionNote(
            id=f"{CRAFT_NOTE_PREFIX}{item.chapter_id}",
            priority="major",
            category="voice_style",
            evidence=f"Observed in this chapter: {'; '.join(item.observations)}.",
            instruction=(
                "Rewrite for a general reader without changing any event: "
                + "; ".join(_REMEDIES[line] for line in item.observations)
                + "."
            ),
            chapter_ids=[item.chapter_id],
        )
        for item in evidence.chapters
        if item.observations
    ]


_REMEDIES = {
    NO_DIALOGUE: "stage the decisive exchange as spoken dialogue",
    RARE_DIALOGUE: "play the key exchange as spoken scene instead of reporting it",
    BLOCK_PARAGRAPHS: "break the paragraphs at each new speaker or shift of attention",
    REPEATED_NAMES: (
        "name a character once when they enter and then let the verb, a pronoun or a concrete "
        "description carry the subject"
    ),
    EMOTION_TAGS: "cut the tags that explain how a line was said and keep a gesture or nothing",
    SIMILE_CHAINS: "keep at most one comparison per paragraph and cut ornamental adjectives",
}
