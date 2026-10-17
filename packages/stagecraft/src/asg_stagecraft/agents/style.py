"""The style contract for every agent whose text a reader sees.

Added in 7.12 after the first readers outside the project found the stories "super rebuscado,
pesadisimo de leer" and noticed names repeated in every line. No prompt asked for readable prose
or said anything about names, and in two narrative runs the Drama Critic raised no note, so the
first draft shipped untouched. Measured there: a dialogue tag explaining the emotion after most
lines, similes in chains, and one character named 45 times in about 3,000 words.

Only the Drafter, the Writer and the Narrator receive it; planners and critics do not write
prose. Like the rest of the pipeline, it carries no figure: a number here would compete with the
qualitative profile, and the model would obey the number.

7.17 adds, behind the style_examples option, two short passages that show what the contract
says. The prompting guides for this model family and the style-imitation literature agree that
a few examples steer register better than a growing list of things not to do, and that two are
about as many as help. They tell no story and name nobody, so a model that copies one copies a
gesture, not a plot; the line editor flags a copied run of words all the same.
"""

from ..schemas import StoryRequest
from ..writing.language import language_code

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

# Written for this contract, in Spanish only: every measured run was in Spanish, and an example
# in another language would teach that language's conventions wrongly.
STYLE_EXAMPLES = (
    "—¿Cerraste la puerta?\n\n"
    "—Dos veces.\n\n"
    "La vecina dejó la taza en el fregadero sin enjuagarla. Se secó las manos en el delantal y "
    "no se dio la vuelta.\n\n"
    "—Entonces, ¿quién sube por la escalera?",
    "El mercado cerraba al mediodía. Quedaban dos puestos abiertos y un perro dormido debajo de "
    "una mesa. El chico contó las monedas otra vez: le faltaba una. Miró el pan, miró al "
    "panadero, y se guardó las monedas en el bolsillo.",
)


def style_clause(request: StoryRequest, *, examples: bool = False) -> str:
    """The shared style contract, its examples when asked for, and the author's own words."""
    clause = f" {READER_PROSE_STYLE}"
    if examples and language_code(request.language) == "es":
        shown = "\n---\n".join(STYLE_EXAMPLES)
        clause += (
            " Two passages written to this contract follow. They show how the prose should "
            "sound, never what to tell: borrow nothing from them, not a word, a gesture or a "
            f"situation.\n---\n{shown}\n---\n"
        )
    if request.style_request.strip():
        clause += (
            " The author asked for this way of writing, in their own words; follow it, and let "
            f"it win over anything above about register and vocabulary: "
            f"{request.style_request.strip()}"
        )
    return clause
