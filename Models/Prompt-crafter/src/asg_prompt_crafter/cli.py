"""Interfaz de línea de comandos."""

import sys
from .agent import PromptCrafterAgent
from .config import load_settings
from .errors import PromptCrafterError
from .provider import GeminiProvider
from .schemas import CraftResult

def render_result(result: CraftResult) -> None:
    print("\nAlternativas mejoradas:\n")
    for index, alternative in enumerate(result.alternatives, start=1):
        recommended = " — RECOMENDADA" if alternative.id == result.recommended_id else ""
        print(f"{index}. {alternative.name} [{alternative.id}]{recommended}")
        print(f"   Enfoque: {alternative.creative_direction}\n")
        print(alternative.prompt)
        print()
    print(f"Recomendación: {result.recommendation_reason}")

def main() -> int:
    print("Prompt-crafter — enriquecedor de ideas narrativas")
    try:
        prompt = input("Describe la historia que quieres mejorar:\n> ").strip()
        if not prompt:
            print("Error: el prompt no puede estar vacío.", file=sys.stderr)
            return 2
        settings = load_settings()
        provider = GeminiProvider(settings.api_key, settings.model)
        print(f"\nCreando alternativas con {settings.model}...")
        render_result(PromptCrafterAgent(provider).craft(prompt))
        return 0
    except (PromptCrafterError, KeyboardInterrupt) as exc:
        message = str(exc) if str(exc) else "operación cancelada"
        print(f"\nError: {message}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
