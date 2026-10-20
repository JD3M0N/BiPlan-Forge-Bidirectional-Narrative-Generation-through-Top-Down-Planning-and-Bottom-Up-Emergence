"""The line editor's acceptance rules: an edit ships only when the code finds it better (7.17)."""

import pytest
from asg_stagecraft.writing.line_edit import check_edit

TAGGED = "—Ven —dijo Ana, sonriendo."
STOCK = "Ana dio un paso al frente y abrió la puerta."
MINUTES = "Ana ordenó a Bruno que callara, preguntando por el mapa."
PASTED = "Ana apuñala la madera del mástil con fuerza."
DIRECTION = "apuñala la madera del mástil con fuerza"


@pytest.mark.parametrize(
    ("original", "replacement", "reason"),
    [
        (TAGGED, "—Ven —dijo Ana.", ""),
        (STOCK, "Ana abrió la puerta de la casa vieja del final de la calle de siempre.", "longer"),
        (STOCK, STOCK, "not reduced"),
        (STOCK, "Ana abrió la puerta a Pedro.", "someone new"),
        (MINUTES, "Ana pidió silencio.\n\n—¿Y el mapa?", "line of dialogue"),
        (TAGGED, "—Ven ya.", "new words"),
        (STOCK, "Ana caminaba y abría la puerta.", "tense"),
        (PASTED, "Ana clavó la daga en el mástil.", ""),
        (PASTED, "Luego Ana apuñala la madera del mástil.", "not reduced"),
    ],
    ids=[
        "fewer-observations",
        "longer",
        "unchanged",
        "invented-name",
        "invented-line",
        "words-put-in-a-mouth",
        "tense",
        "direction-retold",
        "direction-still-pasted",
    ],
)
def test_an_edit_ships_only_when_it_helps_and_changes_nothing_else(original, replacement, reason):
    found = check_edit(
        original,
        replacement,
        names=["Ana"],
        known_names={"Ana", "Bruno"},
        directions=(DIRECTION,),
    )
    assert (reason in found) if reason else found == ""
