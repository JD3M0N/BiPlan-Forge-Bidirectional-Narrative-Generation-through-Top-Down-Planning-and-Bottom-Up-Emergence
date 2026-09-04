"""Command-line interface for Top-Down generation."""

import argparse
import sys

from .config import load_settings
from .errors import ASGError
from .generator import StoryGenerator
from .progress import format_progress
from .provider import GeminiProvider

EXAMPLE_PROMPT = (
    "Escribe un relato de ciencia ficción con perfil narrativo Desarrollada. Una cartógrafa "
    "descubre que las estrellas están cambiando de posición para formar un "
    "mensaje. Tono melancólico, ambientado en una estación orbital decadente y "
    "con un final esperanzador."
)


def parser() -> argparse.ArgumentParser:
    """Build the Top-Down command-line argument parser."""
    result = argparse.ArgumentParser(
        description="Genera una historia mediante el pipeline Top-Down"
    )
    result.add_argument(
        "prompt",
        nargs="?",
        help="Solicitud narrativa; si se omite se pide de forma interactiva",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entry point."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    print("Generador automático de historias — Top-Down")
    print("\nEjemplo de prompt ideal:\n")
    print(f"  {EXAMPLE_PROMPT}\n")
    try:
        prompt = (args.prompt or input("Describe la historia que quieres generar:\n> ")).strip()
        if not prompt:
            print("Error: el prompt no puede estar vacío.", file=sys.stderr)
            return 2
        settings = load_settings()
        provider = GeminiProvider(
            settings.api_key,
            settings.model,
            rpm_limit=settings.rpm_limit,
            rpm_reserve=settings.rpm_reserve,
            tpm_limit=settings.tpm_limit,
            max_retries=settings.max_retries,
            max_retry_delay=settings.max_retry_delay,
            request_timeout_ms=settings.request_timeout_ms,
        )
        generator = StoryGenerator(provider, settings.output_root)

        def report_progress(update) -> None:
            """Print one formatted pipeline progress update."""
            print(format_progress(update), flush=True)

        def report_event(event) -> None:
            """Print one structured pipeline event message."""
            print(event.message, flush=True)

        print(f"\nGenerando con {settings.model}...")
        output = generator.generate(
            prompt,
            on_progress=report_progress,
            on_event=report_event,
        )
        print(f"\nHistoria terminada: {output.story_path}")
        if output.audio_path.is_file():
            print(f"Audio disponible en: {output.audio_path}")
        else:
            print("Advertencia: la historia se guardó, pero no fue posible crear el audio.")
        return 0
    except (ASGError, KeyboardInterrupt) as exc:
        message = exc.public_message() if isinstance(exc, ASGError) else "operación cancelada"
        print(f"\nError: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
