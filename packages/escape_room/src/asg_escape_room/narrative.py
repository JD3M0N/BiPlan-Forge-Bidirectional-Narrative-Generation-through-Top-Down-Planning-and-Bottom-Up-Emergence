"""Decoupled narrative generation with a deterministic fallback."""

from __future__ import annotations

import json

from .contracts import EventLog, NarrativeProvider, SimulationResult


class GeminiNarrativeProvider:
    """Represent GeminiNarrativeProvider data and behavior."""

    def __init__(self, api_key: str, model_name: str) -> None:
        """Initialize the GeminiNarrativeProvider instance."""
        from google import genai

        self.model_name = model_name
        self._client = genai.Client(api_key=api_key)

    def generate_text(self, *, system_instruction: str, prompt: str) -> str:
        """Generate text."""
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction, temperature=0.7
            ),
        )
        if not response.text or not response.text.strip():
            raise RuntimeError("Gemini devolvió una respuesta vacía")
        return response.text.strip()


def relevant_timeline(log: EventLog) -> list[dict]:
    """Handle the relevant timeline operation for component."""
    important = {"pickup", "puzzle_solved", "communication", "escaped"}
    return [event.model_dump(mode="json") for event in log.events if event.kind in important]


def generate_story(
    result: SimulationResult,
    log: EventLog,
    provider: NarrativeProvider | None = None,
) -> tuple[str, str, str | None]:
    """Return the story, narrator source, and optional generation error."""
    if provider is not None:
        try:
            prompt = json.dumps(
                {
                    "result": result.model_dump(mode="json"),
                    "causal_timeline": relevant_timeline(log),
                },
                ensure_ascii=False,
                indent=2,
            )
            story = provider.generate_text(
                system_instruction=(
                    "Escribe una crónica narrativa breve en español y tercera persona "
                    "sobre este escape room. Respeta estrictamente los hechos y su "
                    "orden causal. Destaca descubrimientos y cooperación, evita listar "
                    "ticks, no inventes personajes ni sucesos y devuelve solo Markdown."
                ),
                prompt=prompt,
            )
            return story, "gemini", None
        except Exception as exc:  # El respaldo forma parte del contrato.
            error = str(exc)
    else:
        error = "Proveedor Gemini no configurado"
    outcome = "lograron escapar" if result.success else "no alcanzaron la salida antes del límite"
    lines = [
        "# La habitación de la linterna",
        "",
        f"Los exploradores {outcome} después de {result.ticks} turnos.",
        "",
    ]
    for event in relevant_timeline(log):
        lines.append(event["description"])
    return "\n\n".join(lines), "fallback", error
