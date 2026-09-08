"""Guided-prompt text and Telegram-safe story composition."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .contract import ProfileOption

GUIDED_FIELDS = (
    ("language", "¿En qué idioma quieres la historia?"),
    ("genre", "¿Cuál será el género?"),
    ("protagonist", "Describe al protagonista."),
    ("conflict", "¿Cuál es el conflicto principal?"),
    ("setting", "¿Dónde y cuándo ocurre?"),
    ("tone", "¿Qué tono debe tener?"),
    (
        "narrative_profile",
        "¿Qué perfil narrativo prefieres? {profiles} o Automático.",
    ),
    (
        "constraints",
        "Indica restricciones adicionales o escribe «ninguna».",
    ),
)

AUTOMATIC_PROFILE = "automatic"
AUTOMATIC_ALIASES = frozenset({"automático", "automatico", "automatic", "auto"})
PROFILE_FIELD = "narrative_profile"


@dataclass(frozen=True)
class MetricExplanation:
    """Represent MetricExplanation data and behavior."""

    name: str
    description: str
    low: str
    high: str

    def message(self) -> str:
        """Handle the message operation for MetricExplanation."""
        return (
            f"<b>{html.escape(self.name)}</b>\n"
            f"{html.escape(self.description)}\n\n"
            f"1 — {html.escape(self.low)}\n"
            f"10 — {html.escape(self.high)}"
        )


METRIC_EXPLANATIONS = {
    "coherence": MetricExplanation(
        "Coherencia",
        "Conexión lógica entre los eventos y progresión causal sin huecos.",
        "Incoherente",
        "Totalmente coherente",
    ),
    "pacing": MetricExplanation(
        "Ritmo",
        "Equilibrio entre inicio, nudo y desenlace, información y tensión.",
        "Muy desequilibrado",
        "Excelente y bien dosificado",
    ),
    "creativity": MetricExplanation(
        "Creatividad",
        "Originalidad, ideas valiosas y elementos inesperados.",
        "Nada original",
        "Muy original",
    ),
    "engagement": MetricExplanation(
        "Interés",
        "Capacidad de mantener tu atención y generar impacto emocional.",
        "No mantiene el interés",
        "Muy cautivadora",
    ),
    "relevance": MetricExplanation(
        "Relevancia",
        "Fidelidad a la solicitud original y al tema pedido.",
        "No corresponde al prompt",
        "Completamente fiel al prompt",
    ),
    "satisfaction": MetricExplanation(
        "Satisfacción",
        "Valoración global de cuánto cumplió la historia tus expectativas.",
        "Insatisfecho",
        "Muy satisfecho",
    ),
}

HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


def guided_question(index: int, profiles: tuple[ProfileOption, ...]) -> str:
    """Return one guided question, naming the profiles the generator offers."""
    field, question = GUIDED_FIELDS[index]
    if field != PROFILE_FIELD:
        return question
    return question.format(profiles=", ".join(option.label for option in profiles))


def validate_guided_value(field: str, value: str, profiles: tuple[ProfileOption, ...] = ()) -> str:
    """Normalize one guided answer, rejecting values the field cannot accept."""
    normalized = value.strip()
    if not normalized:
        raise ValueError("La respuesta no puede estar vacía.")
    if field == PROFILE_FIELD:
        return _resolve_profile(normalized, profiles)
    return normalized


def _resolve_profile(value: str, profiles: tuple[ProfileOption, ...]) -> str:
    """Map a user answer onto a profile value, or onto automatic selection."""
    normalized = value.casefold()
    if normalized in AUTOMATIC_ALIASES:
        return AUTOMATIC_PROFILE
    for option in profiles:
        if normalized == option.value.casefold() or normalized in option.aliases:
            return option.value
    choices = ", ".join(option.label for option in profiles)
    raise ValueError(f"Elige {choices} o Automático.")


def build_guided_prompt(values: dict[str, str], profiles: tuple[ProfileOption, ...] = ()) -> str:
    """Compose one free-form prompt out of the collected guided answers."""
    constraints = values["constraints"]
    if constraints.casefold() == "ninguna":
        constraints = "Sin restricciones adicionales."
    profile = values[PROFILE_FIELD]
    label = next((option.label for option in profiles if option.value == profile), None)
    profile_text = "" if label is None else f" Perfil narrativo: {label}."
    return (
        f"Escribe una historia en {values['language']}.{profile_text} Género: {values['genre']}. "
        f"Protagonista: {values['protagonist']}. Conflicto principal: "
        f"{values['conflict']}. Ambientación: {values['setting']}. "
        f"Tono: {values['tone']}. Restricciones: {constraints}"
    )


def _take_safe_prefix(text: str, limit: int) -> tuple[str, str]:
    """Take a text prefix without splitting escaped HTML entities."""
    used = 0
    last_space = -1
    for index, character in enumerate(text):
        escaped_length = len(html.escape(character))
        if used + escaped_length > limit:
            boundary = last_space if last_space > 0 else index
            if boundary == 0:
                boundary = 1
            return text[:boundary], text[boundary:].lstrip()
        used += escaped_length
        if character.isspace():
            last_space = index
    return text, ""


def _render_block(text: str, bold: bool, limit: int) -> list[str]:
    """Render block."""
    wrapper = 7 if bold else 0
    available = limit - wrapper
    if available < 1:
        raise ValueError("limit es demasiado pequeño para el formato")
    rendered: list[str] = []
    remaining = text
    while remaining:
        piece, remaining = _take_safe_prefix(remaining, available)
        escaped = html.escape(piece)
        rendered.append(f"<b>{escaped}</b>" if bold else escaped)
    return rendered or ["<b></b>" if bold else ""]


def telegram_story_chunks(markdown: str, limit: int = 3900) -> list[str]:
    """Convert Markdown headings into safe HTML message chunks."""
    if limit < 8:
        raise ValueError("limit debe ser al menos 8")
    blocks: list[tuple[str, bool]] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        """Flush paragraph."""
        if paragraph:
            blocks.append(("\n".join(paragraph), False))
            paragraph.clear()

    for line in markdown.splitlines():
        heading = HEADING.match(line)
        if heading:
            flush_paragraph()
            blocks.append((heading.group(1), True))
        elif not line.strip():
            flush_paragraph()
        else:
            paragraph.append(line)
    flush_paragraph()

    messages: list[str] = []
    current = ""
    for raw, bold in blocks:
        for rendered in _render_block(raw, bold, limit):
            candidate = f"{current}\n\n{rendered}" if current else rendered
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    messages.append(current)
                current = rendered
    if current or not messages:
        messages.append(current)
    return messages
