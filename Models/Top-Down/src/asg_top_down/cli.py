"""Interfaz de línea de comandos."""

import sys

from .config import load_settings
from .errors import ASGError
from .orchestrator import StoryOrchestrator
from .progress import format_progress
from .provider import GeminiProvider

EXAMPLE_PROMPT = (
    "Escribe un relato de ciencia ficción de unas 1800 palabras. Una cartógrafa "
    "descubre que las estrellas están cambiando de posición para formar un "
    "mensaje. Tono melancólico, ambientado en una estación orbital decadente y "
    "con un final esperanzador."
)


def main() -> int:
    print("Generador automático de historias — Top-Down")
    print("\nEjemplo de prompt ideal:\n")
    print(f"  {EXAMPLE_PROMPT}\n")
    try:
        prompt = input("Describe la historia que quieres generar:\n> ").strip()
        if not prompt:
            print("Error: el prompt no puede estar vacío.", file=sys.stderr)
            return 2
        settings = load_settings()
        provider = GeminiProvider(settings.api_key, settings.model)
        orchestrator = StoryOrchestrator(provider, settings.output_root)
        print(f"\nGenerando con {settings.model}...")
        output = orchestrator.run(
            prompt,
            on_progress=lambda update: print(
                f"\r{format_progress(update)}", end="", flush=True
            ),
        )
        print()
        print(f"\nHistoria terminada: {output / 'story.md'}")
        return 0
    except (ASGError, KeyboardInterrupt) as exc:
        message = str(exc) if str(exc) else "operación cancelada"
        print(f"\nError: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
