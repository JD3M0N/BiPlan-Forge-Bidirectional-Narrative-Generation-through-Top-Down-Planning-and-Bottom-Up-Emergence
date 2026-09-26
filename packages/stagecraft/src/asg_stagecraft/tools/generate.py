"""Command-line interface for Stagecraft story generation."""

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from ..formats import ActorMemory, NarrativeVoice, ScriptMethod, StoryFormat
from ..generator import StoryGenerator
from ..planning.profiles import NarrativeProfile
from ..runtime.config import load_settings
from ..runtime.errors import ASGError
from ..runtime.progress import format_progress
from ..runtime.provider import provider_from_settings

EXAMPLE_PROMPT = (
    "Escribe un relato de ciencia ficción con perfil narrativo Desarrollada. Una cartógrafa "
    "descubre que las estrellas están cambiando de posición para formar un "
    "mensaje. Tono melancólico, ambientado en una estación orbital decadente y "
    "con un final esperanzador."
)


def parser() -> argparse.ArgumentParser:
    """Build the Stagecraft command-line argument parser."""
    result = argparse.ArgumentParser(
        description="Genera una historia mediante el pipeline Stagecraft"
    )
    result.add_argument(
        "prompt",
        nargs="?",
        help="Solicitud narrativa; si se omite se pide de forma interactiva",
    )
    result.add_argument(
        "--profile",
        type=NarrativeProfile,
        choices=list(NarrativeProfile),
        help="Fuerza el perfil narrativo y manda sobre el que se deduzca del prompt",
    )
    result.add_argument(
        "--output",
        type=Path,
        help="Directorio raíz donde se guarda la ejecución",
    )
    result.add_argument(
        "--model",
        help="Modelo de Gemini a utilizar en lugar del configurado en .env",
    )
    result.add_argument(
        "--no-audio",
        action="store_true",
        help="Omite la narración en audio, que domina el tiempo de una tanda de experimentos",
    )
    result.add_argument(
        "--format",
        dest="story_format",
        type=StoryFormat,
        choices=list(StoryFormat),
        help="Formato de salida: historia narrativa o guion teatral",
    )
    result.add_argument(
        "--script-method",
        type=ScriptMethod,
        choices=list(ScriptMethod),
        help="Con --format script: escrito por escenas o adaptado de la prosa final",
    )
    result.add_argument(
        "--voice",
        dest="narrative_voice",
        type=NarrativeVoice,
        choices=list(NarrativeVoice),
        help="Con --format simulated: punto de vista desde el que se narra la funcion",
    )
    result.add_argument(
        "--actor-memory",
        type=ActorMemory,
        choices=list(ActorMemory),
        help=(
            "Con --format simulated: 'own' da a cada personaje solo lo que presencio, "
            "'shared' reparte todo lo publico y sirve de brazo de control"
        ),
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entry point."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    args = parser().parse_args(argv)
    print("Generador automático de historias — Stagecraft")
    print("\nEjemplo de prompt ideal:\n")
    print(f"  {EXAMPLE_PROMPT}\n")
    try:
        prompt = (args.prompt or input("Describe la historia que quieres generar:\n> ")).strip()
        if not prompt:
            print("Error: el prompt no puede estar vacío.", file=sys.stderr)
            return 2
        settings = load_settings()
        if args.model:
            settings = replace(settings, model=args.model)
        if args.output:
            settings = replace(settings, output_root=args.output)
        provider = provider_from_settings(settings)
        generator = StoryGenerator(
            provider,
            settings.output_root,
            narrative_guidance=settings.narrative_guidance,
            promise_ledger=settings.promise_ledger,
            narrative_profile=args.profile,
            audio=not args.no_audio,
            story_format=args.story_format or settings.story_format,
            script_method=args.script_method or settings.script_method,
            narrative_voice=args.narrative_voice or settings.narrative_voice,
            actor_memory=args.actor_memory or settings.actor_memory,
            turns_per_beat=settings.turns_per_beat,
        )

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
        if output.story_format is StoryFormat.SCRIPT:
            print(f"\nGuion terminado: {output.story_path}")
            print(f"Guion estructurado: {output.script_path}")
        else:
            print(f"\nHistoria terminada: {output.story_path}")
        if output.audio_path.is_file():
            print(f"Audio disponible en: {output.audio_path}")
        elif not args.no_audio:
            print("Advertencia: la historia se guardó, pero no fue posible crear el audio.")
        return 0
    except (ASGError, KeyboardInterrupt) as exc:
        message = exc.public_message() if isinstance(exc, ASGError) else "operación cancelada"
        print(f"\nError: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
