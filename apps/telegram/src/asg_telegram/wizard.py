"""Pure rendering for the guided story-brief wizard: no I/O, only text and keyboards."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .contract import BriefSpec, CastEntry, StoryOutline

BRIEF_STEPS = ("title", "genre", "setting", "plot", "cast", "notes", "confirm")
MEMBER_STEPS = ("name", "role", "pronoun", "description", "secret")
SKIPPABLE_STEPS = frozenset({"title", "genre", "setting", "notes", "description", "secret"})

_QUESTIONS = {
    "title": "¿Qué título provisional quieres? Puedes omitirlo.",
    "genre": "¿Cuál es el género? Puedes omitirlo.",
    "setting": "¿Dónde y cuándo ocurre? Puedes omitirlo.",
    "plot": "Cuéntame la trama.",
    "notes": ("¿Alguna nota más: idioma, tono o restricciones? Puedes omitirla."),
    "name": "¿Cómo se llama este personaje?",
    "description": "Descríbelo brevemente. Puedes omitirlo.",
    "secret": "¿Tiene algún secreto? Puedes omitirlo.",
}


def question(step: str, spec: BriefSpec) -> str:
    """Return the question shown for one wizard step, with its length limit stated."""
    text = _QUESTIONS[step]
    limit = spec.limits.get(step)
    return f"{text} (máximo {limit} caracteres)" if limit else text


def check_length(field: str, text: str, spec: BriefSpec) -> str:
    """Trim and validate one free-text answer against the brief's declared limits."""
    trimmed = text.strip()
    limit = spec.limits.get(field)
    if limit and len(trimmed) > limit:
        raise ValueError(f"Ese texto supera los {limit} caracteres permitidos.")
    return trimmed


def skip_keyboard(step: str) -> InlineKeyboardMarkup:
    """Build the keyboard offered on a step that may be left empty."""
    button = InlineKeyboardButton("Omitir", callback_data=f"brief:skip:{step}")
    return InlineKeyboardMarkup([[button]])


def role_keyboard(spec: BriefSpec) -> InlineKeyboardMarkup:
    """Build the keyboard listing every role a cast member may declare."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(choice.label, callback_data=f"brief:role:{index}")]
            for index, choice in enumerate(spec.roles)
        ]
    )


def pronoun_keyboard(spec: BriefSpec) -> InlineKeyboardMarkup:
    """Build the keyboard listing every pronoun a cast member may declare."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(choice.label, callback_data=f"brief:pron:{index}")]
            for index, choice in enumerate(spec.pronouns)
        ]
    )


def cast_keyboard(count: int, spec: BriefSpec) -> InlineKeyboardMarkup:
    """Build the keyboard shown once a cast member is complete."""
    rows = []
    if count < spec.max_cast:
        rows.append([InlineKeyboardButton("➕ Añadir personaje", callback_data="brief:add")])
    if count:
        rows.append([InlineKeyboardButton("↩ Quitar el último", callback_data="brief:undo")])
    rows.append([InlineKeyboardButton("Continuar", callback_data="brief:next")])
    return InlineKeyboardMarkup(rows)


def confirm_keyboard() -> InlineKeyboardMarkup:
    """Build the keyboard shown on the final brief confirmation card."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🚀 Generar", callback_data="brief:go")],
            [InlineKeyboardButton("⚙️ Opciones", callback_data="brief:opts")],
            [InlineKeyboardButton("✏️ Empezar de nuevo", callback_data="brief:restart")],
        ]
    )


def outline_from(values: dict) -> StoryOutline:
    """Build a StoryOutline from the wizard's collected answers."""
    cast = tuple(CastEntry(**member) for member in values.get("cast", []))
    return StoryOutline(
        plot=values.get("plot", ""),
        title=values.get("title", ""),
        genre=values.get("genre", ""),
        setting=values.get("setting", ""),
        cast=cast,
        notes=values.get("notes", ""),
    )


def _cast_summary(outline: StoryOutline) -> str:
    """Render one line per declared cast member, for the confirmation card."""
    lines = []
    for member in outline.cast:
        detail = ", ".join(part for part in (member.role, member.pronoun) if part)
        lines.append(f"  · {member.name}" + (f" ({detail})" if detail else ""))
    return "\n".join(lines)


def outline_summary(outline: StoryOutline, *, limit: int = 3500) -> str:
    """Render the outline as a confirmation card, staying under Telegram's message limit."""
    lines = ["<b>Revisa la obra</b>", ""]
    if outline.title:
        lines.append(f"Título: {outline.title}")
    if outline.genre:
        lines.append(f"Género: {outline.genre}")
    if outline.setting:
        lines.append(f"Ambientación: {outline.setting}")
    lines.append(f"Trama: {outline.plot}")
    if outline.cast:
        lines.append(f"Reparto ({len(outline.cast)}):")
        lines.append(_cast_summary(outline))
    if outline.notes:
        lines.append(f"Notas: {outline.notes}")
    text = "\n".join(lines)
    if len(text) > limit:
        text = text[: limit - 20].rstrip() + "\n[…recortado…]"
    return text
