"""The style contract for every agent whose text a reader sees.

Added in 7.12 after the first readers outside the project found the stories "super rebuscado,
pesadisimo de leer" and noticed names repeated in every line. No prompt asked for readable prose
or said anything about names, and in two narrative runs the Drama Critic raised no note, so the
first draft shipped untouched. Measured there: a dialogue tag explaining the emotion after most
lines, similes in chains, and one character named 45 times in about 3,000 words.

Only the Drafter, the Writer and the Narrator receive it; planners and critics do not write
prose. Like the rest of the pipeline, it carries no figure: a number here would compete with the
qualitative profile, and the model would obey the number.
"""

from ..schemas import StoryRequest

READER_PROSE_STYLE = (
    "STYLE FOR THE READER: write plain, clear prose a general reader follows without effort: "
    "everyday words, short and medium sentences, one idea per sentence; the writing should not "
    "be noticed. Name a character when they enter a scene or when the subject would otherwise "
    "be unclear; after that let the verb carry the subject, as the language allows, or use a "
    "pronoun or a concrete description, and never repeat a name in consecutive sentences. "
    "Attribute a line with a plain speech verb or not at all, and never follow it with a tag "
    "that explains the emotion ('with a mixture of...', 'with jovial urgency'): show it with a "
    "gesture or leave it out. Use at most one image or comparison in a paragraph and do not "
    "stack adjectives. Keep a character's gesture and their line in the same paragraph."
)


def style_clause(request: StoryRequest) -> str:
    """The shared style contract, followed by the author's own words when they gave any."""
    clause = f" {READER_PROSE_STYLE}"
    if request.style_request.strip():
        clause += (
            " The author asked for this way of writing, in their own words; follow it, and let "
            f"it win over anything above about register and vocabulary: "
            f"{request.style_request.strip()}"
        )
    return clause
