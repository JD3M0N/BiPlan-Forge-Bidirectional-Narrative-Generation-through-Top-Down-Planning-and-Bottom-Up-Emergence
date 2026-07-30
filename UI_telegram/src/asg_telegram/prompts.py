"""Textos y composición del asistente guiado."""

from __future__ import annotations

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

METRIC_EXPLANATIONS = {
    "coherence": (
        "Coherencia: sentido global, conexión lógica entre los eventos y "
        "progresión causal sin huecos."
    ),
    "pacing": (
        "Ritmo: equilibrio entre inicio, nudo y desenlace, y buena "
        "dosificación de información y tensión."
    ),
    "creativity": (
        "Creatividad: originalidad, ideas valiosas y elementos inesperados "
        "sin depender demasiado de clichés."
    ),
    "engagement": (
        "Interés: capacidad de mantener tu atención, disfrute e impacto "
        "emocional de principio a fin."
    ),
    "relevance": (
        "Relevancia: fidelidad a la solicitud original y ausencia de "
        "elementos fuera de lugar."
    ),
    "satisfaction": (
        "Satisfacción: valoración global de cuánto cumplió la historia tus "
        "expectativas."
    ),
}


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
