"""Interfaz de línea de comandos."""

import sys

from .config import load_settings
from .errors import ASGError
from .generator import StoryGenerator
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
        provider = GeminiProvider(
            settings.api_key, settings.model,
            rpm_limit=settings.rpm_limit, rpm_reserve=settings.rpm_reserve,
            tpm_limit=settings.tpm_limit, max_retries=settings.max_retries,
            max_retry_delay=settings.max_retry_delay,
            embedding_model=settings.embedding_model,
        )
        orchestrator = StoryGenerator(
            provider, settings.output_root,
            default_target_words=settings.default_target_words,
            max_cpn_retries=settings.max_cpn_retries,
        )
        print(f"\nGenerando con {settings.model}...")
        output = orchestrator.run(
            prompt,
            on_progress=lambda update: print(
                f"\r{format_progress(update)}", end="", flush=True
            ),
        )
        print()
        print(f"\nHistoria terminada: {output.story_path}")
        return 0
    except (ASGError, KeyboardInterrupt) as exc:
        message = exc.public_message() if isinstance(exc, ASGError) else "operación cancelada"
        print(f"\nError: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
