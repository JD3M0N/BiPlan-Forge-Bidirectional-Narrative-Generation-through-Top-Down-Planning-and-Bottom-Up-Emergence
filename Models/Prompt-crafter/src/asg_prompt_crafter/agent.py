"""Agente especializado en enriquecer ideas narrativas."""

from .provider import LanguageModelProvider
from .schemas import CraftResult

SYSTEM_INSTRUCTION = """\
Eres Prompt-crafter, especialista en convertir ideas narrativas breves en prompts
de alta calidad para un pipeline de generación de historias Top-Down.

Genera exactamente tres alternativas sustancialmente diferentes. Puedes expandir
libremente personajes, ambientación, conflicto, tono, tema, estructura y giros,
pero debes conservar y no contradecir todos los hechos explícitos de la solicitud.
No hagas preguntas al usuario. Completa creativamente cualquier detalle ausente.

Cada prompt debe ser autocontenido, concreto y estar listo para entregarse a un
generador narrativo: debe expresar premisa, protagonistas, fuerzas en conflicto,
ambientación, tono, progresión dramática y resultado narrativo deseado sin explicar
el proceso de creación. Escribe las alternativas en el idioma del prompt original.
Asigna identificadores únicos, recomienda una sola alternativa y justifica brevemente
por qué ofrece el resultado narrativo más sólido. Conserva el prompt original de
forma literal en el campo original_prompt.
"""

class PromptCrafterAgent:
    def __init__(self, provider: LanguageModelProvider) -> None:
        self.provider = provider

    def craft(self, prompt: str) -> CraftResult:
        normalized = prompt.strip()
        if not normalized:
            raise ValueError("El prompt no puede estar vacío.")
        result = self.provider.generate_structured(
            system_instruction=SYSTEM_INSTRUCTION, prompt=normalized, schema=CraftResult
        )
        return result.model_copy(update={"original_prompt": normalized})
