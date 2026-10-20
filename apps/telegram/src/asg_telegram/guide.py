"""What the bot tells each participant to do next, and the menus that get them there.

The study needs one story of each model from the same person, ideally on the same idea, and
then that person's comparison of the two. So the bot always recommends the next step: a
Top-Down story first, the same idea with the hybrid model next, and then the comparison.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .generator import METHODS

MODES = {"free": ("✍️", "Libre"), "guided": ("🧭", "Guiada")}
WELCOME = (
    "Hola. Este bot escribe historias con los dos modelos de una tesis y te pide que las "
    "compares.\n\n"
    "Te recomendamos crear dos historias con la misma idea: primero con Top-Down y después "
    "con el Híbrido. Así, al compararlas, lo único que cambia es el modelo.\n\n"
    "• Top-Down: planifica la trama completa y después la escribe.\n"
    "• Híbrido: los personajes representan la obra, cada uno con su propia memoria, y después "
    "se narra lo que hicieron. Tarda bastante más.\n"
    "• Libre: escribes tu idea en un mensaje.\n"
    "• Guiada: título, género, ambientación, trama y personajes, paso a paso.\n\n"
    "/crear: nueva historia\n"
    "/evaluar: comparar tus dos historias\n"
    "/cancelar: cancelar lo que estés haciendo"
)
CHOOSE = (
    "¿Cómo la creamos? Si es tu primera historia, empieza por Top-Down: después te propondré "
    "la misma idea con el Híbrido."
)


def keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """Build an inline keyboard from (label, callback data) pairs."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )


def option_label(story_format: str, mode: str) -> str:
    """Name one of the four ways to create a story."""
    icon, name = MODES[mode]
    return f"{icon} {name} · {METHODS[story_format]}"


CREATE = keyboard(
    [
        [(option_label(story_format, mode), f"c:o:{story_format}:{mode}")]
        for story_format in METHODS
        for mode in MODES
    ]
)
MENU = keyboard([[("✍️ Crear historia", "c:menu")], [("⚖️ Comparar mis historias", "e:go")]])


def other_format(story_format: str) -> str:
    """Return the model a story was not written with."""
    return next(item for item in METHODS if item != story_format)


def next_step(queue, pairs, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Recommend what the participant should do now, with the buttons to do it."""
    if pairs.open_pair(user_id):
        return (
            "Tienes una comparación a medias. Sigue cuando quieras.",
            keyboard([[("⚖️ Seguir comparando", "e:go")]]),
        )
    completed = queue.completed(user_id)
    if pairs.candidate(user_id, completed):
        return (
            "Ya tienes una historia de cada modelo. Compáralas: te haré tres preguntas, sin "
            "notas, solo cuál de las dos prefieres en cada aspecto.",
            keyboard([[("⚖️ Comparar mis dos historias", "e:go")], [("✍️ Crear otra", "c:menu")]]),
        )
    used = pairs.used_jobs(user_id)
    single = next((job for job in completed if job["id"] not in used), None)
    if single is None:
        return "¿Creamos una historia?", CREATE
    missing = other_format(single["story_format"])
    return (
        f"Ahora crea la misma idea con el modelo {METHODS[missing]}, para compararlas después.",
        keyboard(
            [
                [(f"🔁 La misma idea con {METHODS[missing]}", f"c:same:{single['id']}")],
                [("✍️ Otra idea", "c:menu")],
            ]
        ),
    )
