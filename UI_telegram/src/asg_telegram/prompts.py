"""Textos y composición del asistente guiado."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

GUIDED_FIELDS = (
    ("language", "¿En qué idioma quieres la historia?"),
    ("genre", "¿Cuál será el género?"),
    ("protagonist", "Describe al protagonista."),
    ("conflict", "¿Cuál es el conflicto principal?"),
    ("setting", "¿Dónde y cuándo ocurre?"),
    ("tone", "¿Qué tono debe tener?"),
    ("target_words", "¿Cuántas palabras aproximadamente? (300–20000)"),
    (
        "constraints",
        "Indica restricciones adicionales o escribe «ninguna».",
    ),
)

@dataclass(frozen=True)
class MetricExplanation:
    name: str
    description: str
    low: str
    high: str

    def message(self) -> str:
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


def validate_guided_value(field: str, value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("La respuesta no puede estar vacía.")
    if field == "target_words":
        try:
            words = int(normalized)
        except ValueError as exc:
            raise ValueError("Introduce un número entero entre 300 y 20000.") from exc
        if not 300 <= words <= 20_000:
            raise ValueError("Introduce un número entero entre 300 y 20000.")
        return str(words)
    return normalized


def build_guided_prompt(values: dict[str, str]) -> str:
    constraints = values["constraints"]
    if constraints.casefold() == "ninguna":
        constraints = "Sin restricciones adicionales."
    return (
        f"Escribe una historia en {values['language']} de aproximadamente "
        f"{values['target_words']} palabras. Género: {values['genre']}. "
        f"Protagonista: {values['protagonist']}. Conflicto principal: "
        f"{values['conflict']}. Ambientación: {values['setting']}. "
        f"Tono: {values['tone']}. Restricciones: {constraints}"
    )


def split_story(text: str, limit: int = 3900) -> list[str]:
    """Divide texto priorizando párrafos y preservando todo el contenido."""
    if limit < 1:
        raise ValueError("limit debe ser positivo")
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        boundary = remaining.rfind("\n\n", 0, limit + 1)
        if boundary < limit // 2:
            boundary = remaining.rfind("\n", 0, limit + 1)
        if boundary < limit // 2:
            boundary = remaining.rfind(" ", 0, limit + 1)
        if boundary < 1:
            boundary = limit
        chunks.append(remaining[:boundary])
        remaining = remaining[boundary:]
        if remaining.startswith("\n\n"):
            remaining = remaining[2:]
        elif remaining.startswith(("\n", " ")):
            remaining = remaining[1:]
    if remaining or not chunks:
        chunks.append(remaining)
    return chunks


def _take_safe_prefix(text: str, limit: int) -> tuple[str, str]:
    """Corta texto sin partir una entidad HTML generada por escape()."""
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
    """Convierte encabezados Markdown en HTML y crea mensajes HTML seguros."""
    if limit < 8:
        raise ValueError("limit debe ser al menos 8")
    blocks: list[tuple[str, bool]] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
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
