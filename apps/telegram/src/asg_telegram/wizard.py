"""Guided story wizard as a pure state machine: answers in, text and keyboards out."""

from __future__ import annotations

from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .generator import BRIEF_LIMITS, MAX_CAST, PRONOUNS, ROLES, StoryOutline, brief_from

FIELDS = ("title", "genre", "setting", "plot")
OPTIONAL = frozenset({"title", "genre", "setting", "notes", "description", "secret"})
_QUESTIONS = {
    "title": "¿Qué título provisional quieres?",
    "genre": "¿Cuál es el género?",
    "setting": "¿Dónde y cuándo ocurre?",
    "plot": "Cuéntame la trama.",
    "notes": "¿Alguna nota más: tono, idioma o restricciones?",
    "name": "¿Cómo se llama el personaje?",
    "role": "¿Qué papel tiene?",
    "pronoun": "¿Qué pronombre usa?",
    "description": "Descríbelo brevemente.",
    "secret": "¿Guarda algún secreto?",
}


@dataclass
class Reply:
    """What the bot says next, and the outline once the participant confirms it."""

    text: str
    keyboard: InlineKeyboardMarkup | None = None
    outline: StoryOutline | None = None


def _buttons(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """Build an inline keyboard from (label, wizard action) pairs."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=f"w:{data}") for label, data in row]
            for row in rows
        ]
    )


def start() -> tuple[dict, Reply]:
    """Open a new wizard at its first question."""
    state = {"step": "title", "values": {}, "cast": [], "member": {}}
    return state, _ask(state)


def _ask(state: dict) -> Reply:
    """Render the question for the current step."""
    step = state["step"]
    if step == "cast":
        rows = []
        if len(state["cast"]) < MAX_CAST:
            rows.append([("➕ Añadir personaje", "add")])
        rows.append([("Continuar", "next")])
        names = ", ".join(member["name"] for member in state["cast"]) or "ninguno"
        return Reply(f"Personajes: {names}.", _buttons(rows))
    if step == "role":
        return Reply(
            _QUESTIONS[step],
            _buttons([[(label, f"role:{i}")] for i, (_, label) in enumerate(ROLES)]),
        )
    if step == "pronoun":
        return Reply(
            _QUESTIONS[step],
            _buttons([[(label, f"pron:{i}")] for i, (_, label) in enumerate(PRONOUNS)]),
        )
    if step == "confirm":
        return Reply(
            summary(outline(state)),
            _buttons([[("🚀 Generar", "go")], [("✏️ Empezar de nuevo", "restart")]]),
        )
    limit = BRIEF_LIMITS.get(step)
    text = _QUESTIONS[step] + (f" (máximo {limit} caracteres)" if limit else "")
    return Reply(text, _buttons([[("Omitir", "skip")]]) if step in OPTIONAL else None)


def _advance(state: dict) -> Reply:
    """Move to the step after the current one and ask it."""
    step = state["step"]
    order = (*FIELDS, "cast")
    member_order = ("name", "role", "pronoun", "description", "secret")
    if step in FIELDS:
        state["step"] = order[order.index(step) + 1]
    elif step in member_order[:-1]:
        state["step"] = member_order[member_order.index(step) + 1]
    elif step == "secret":
        state["cast"].append(state["member"])
        state["member"] = {}
        state["step"] = "cast"
    elif step == "notes":
        state["step"] = "confirm"
    return _ask(state)


def answer(state: dict, text: str) -> Reply:
    """Store a typed answer for the current step, or explain why it was refused."""
    step = state["step"]
    if step in {"cast", "role", "pronoun", "confirm"}:
        return Reply("Usa los botones para continuar.")
    value = text.strip()
    limit = BRIEF_LIMITS.get(step)
    if limit and len(value) > limit:
        return Reply(f"Ese texto supera los {limit} caracteres permitidos.")
    if not value and step not in OPTIONAL:
        return Reply("Esta respuesta no puede quedar vacía.")
    target = state["member"] if step in {"name", "description", "secret"} else state["values"]
    if step == "name" and any(m["name"].lower() == value.lower() for m in state["cast"]):
        return Reply("Ya hay un personaje con ese nombre.")
    target[step] = value
    return _advance(state)


def press(state: dict, action: str) -> Reply:
    """Apply one button press of the wizard."""
    kind, _, arg = action.partition(":")
    step = state["step"]
    if kind == "skip" and step in OPTIONAL:
        return answer(state, "")
    if kind == "add" and step == "cast" and len(state["cast"]) < MAX_CAST:
        state["step"] = "name"
        return _ask(state)
    if kind == "next" and step == "cast":
        state["step"] = "notes"
        return _ask(state)
    if kind in {"role", "pron"} and step == ("role" if kind == "role" else "pronoun"):
        choices = ROLES if kind == "role" else PRONOUNS
        state["member"][step] = choices[int(arg)][0]
        return _advance(state)
    if kind == "restart":
        state.clear()
        state.update(start()[0])
        return _ask(state)
    if kind == "go" and step == "confirm":
        result = outline(state)
        try:
            brief_from(result)
        except ValueError as exc:
            return Reply(f"{exc}\n\nEmpieza de nuevo con /crear.")
        return Reply("Obra lista.", outline=result)
    return Reply("Ese paso ya no está activo.")


def outline(state: dict) -> StoryOutline:
    """Build the outline from the answers collected so far."""
    values = state["values"]
    return StoryOutline(
        plot=values.get("plot", ""),
        title=values.get("title", ""),
        genre=values.get("genre", ""),
        setting=values.get("setting", ""),
        cast=tuple(state["cast"]),
        notes=values.get("notes", ""),
    )


def summary(story: StoryOutline) -> str:
    """Render the confirmation card in plain text, under Telegram's message limit."""
    lines = ["Revisa la obra:", ""]
    for label, value in (
        ("Título", story.title),
        ("Género", story.genre),
        ("Ambientación", story.setting),
        ("Trama", story.plot),
    ):
        if value:
            lines.append(f"{label}: {value}")
    for member in story.cast:
        lines.append(f"  · {member['name']} ({member['role']}, {member['pronoun']})")
    if story.notes:
        lines.append(f"Notas: {story.notes}")
    text = "\n".join(lines)
    return text if len(text) <= 3500 else text[:3480].rstrip() + "\n[…recortado…]"
