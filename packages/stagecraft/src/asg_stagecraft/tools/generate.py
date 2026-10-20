"""Command-line interface for Stagecraft story generation."""

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from asg_core import NARRATION_VOICE_NAMES, use_utf8_output
from pydantic import ValidationError

from ..brief import StoryBrief
from ..formats import (
    ActorMemory,
    NarrationMethod,
    NarrativeVoice,
    ScriptMethod,
    SimulationMode,
    StoryFormat,
)
from ..generator import StoryGenerator
from ..options import GenerationOptions
from ..planning.catalog_types import GuidanceStrategy
from ..planning.profiles import NarrativeProfile
from ..runtime.config import load_settings
from ..runtime.errors import ASGError
from ..runtime.progress import format_progress
from ..runtime.provider import provider_from_settings
from .budget import preflight

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
        "--stage-model",
        help=(
            "Con --format simulated: modelo de Gemini que prueban primero los actores, en lugar "
            "de GEMINI_STAGE_MODEL; con su propio cupo diario, deja intacto el del pipeline"
        ),
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
    result.add_argument(
        "--simulation-mode",
        type=SimulationMode,
        choices=list(SimulationMode),
        help="Con --format simulated: fixed o adaptive para desviar hitos pendientes",
    )
    result.add_argument(
        "--inventory",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Con --format simulated: da objetos a los personajes y arbitra en codigo quien "
            "tiene que; --no-inventory es su brazo de control"
        ),
    )
    result.add_argument(
        "--narrator",
        help=(
            "Con --voice limited o first_person: el personaje desde el que se narra, por su "
            "nombre; si no aparece en el reparto, narra el protagonista y el run lo avisa"
        ),
    )
    result.add_argument(
        "--tone",
        dest="narration_tone",
        help="Con --format simulated: el registro que se pide al narrador, en texto libre",
    )
    result.add_argument(
        "--narration-method",
        type=NarrationMethod,
        choices=list(NarrationMethod),
        help=(
            "Con --format simulated: reported (7.16) o selected, que elige los momentos antes "
            "de narrar"
        ),
    )
    for flag, help_text in (
        ("--style-examples", "añade al contrato de estilo dos párrafos de muestra"),
        ("--line-editor", "reescribe solo los párrafos que el código marca"),
        ("--scene-cards", "con --format narrative: fichas de escena antes del borrador"),
        ("--anchored-critic", "con --format narrative: el crítico cita lo que juzga"),
        ("--typed-clauses", "con --format simulated: el mundo puede ejecutar viajes y llegadas"),
    ):
        result.add_argument(
            flag, action=argparse.BooleanOptionalAction, default=None, help=help_text
        )
    result.add_argument(
        "--turns-per-beat",
        type=int,
        help=(
            "Con --format simulated: turnos que puede durar un beat antes de que el mundo lo cierre"
        ),
    )
    result.add_argument(
        "--audio-voice",
        choices=sorted(NARRATION_VOICE_NAMES),
        metavar="VOZ",
        help=(
            "Voz de edge-tts que lee story.mp3, p. ej. es-MX-DaliaNeural; sin ella decide el "
            "idioma de la historia"
        ),
    )
    result.add_argument(
        "--plan-from",
        type=Path,
        help=(
            "Reutiliza el plan de un run completo: con --format simulated también el guion y el "
            "casting, y vuelve a representar; con --format narrative escribe otro borrador"
        ),
    )
    result.add_argument(
        "--narrate-from",
        type=Path,
        help=(
            "Vuelve a narrar la función de un run simulado completo sin representarla: unas 12 "
            "llamadas, para comparar dos narraciones del mismo log"
        ),
    )
    result.add_argument(
        "--force",
        action="store_true",
        help="Lanza el run aunque la cuota que queda hoy no alcance para una historia media",
    )
    result.add_argument(
        "--prompt-file",
        type=Path,
        help=(
            "Archivo de texto UTF-8 con el prompt. Evita que Windows PowerShell 5.1 rompa las "
            "tildes al pasar el prompt como argumento"
        ),
    )
    result.add_argument(
        "--brief",
        type=Path,
        help=(
            "Ficha JSON de la obra (trama y reparto) en lugar de un prompt, p. ej. el "
            "brief.json de un run"
        ),
    )
    result.add_argument(
        "--options",
        type=Path,
        help=(
            "Opciones JSON de un run (su generation_options.json) para repetirlo; los demás "
            "flags mandan sobre ellas"
        ),
    )
    result.add_argument(
        "--guidance-strategy",
        type=GuidanceStrategy,
        choices=list(GuidanceStrategy),
        help="Guía narrativa: hybrid_v1 (control) o compositional_v2 (experimental)",
    )
    result.add_argument(
        "--narrative-guidance",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Activa la guía; --no-narrative-guidance omite ambas estrategias",
    )
    return result


def build_options(args: argparse.Namespace, settings) -> GenerationOptions:
    """Combine the settings, a recorded options file and the flags given, the flags winning.

    A recorded file is a whole run's options, so it replaces what the settings say rather than
    merging with them: replaying a run must not depend on today's .env.
    """
    base = (
        GenerationOptions.model_validate_json(args.options.read_text(encoding="utf-8"))
        if args.options
        else GenerationOptions.from_settings(settings)
    )
    flags = {
        "narrative_profile": args.profile,
        "guidance_strategy": args.guidance_strategy,
        "narrative_guidance": args.narrative_guidance,
        "audio": False if args.no_audio else None,
        "audio_voice": args.audio_voice,
        "story_format": args.story_format or (StoryFormat.SIMULATED if _reuses(args) else None),
        "script_method": args.script_method,
        "narrative_voice": args.narrative_voice,
        "narrator": args.narrator,
        "narration_tone": args.narration_tone,
        "actor_memory": args.actor_memory,
        "simulation_mode": args.simulation_mode,
        "inventory": args.inventory,
        "turns_per_beat": args.turns_per_beat,
        "narration_method": args.narration_method,
        "style_examples": args.style_examples,
        "line_editor": args.line_editor,
        "scene_cards": args.scene_cards,
        "anchored_critic": args.anchored_critic,
        "typed_clauses": args.typed_clauses,
    }
    return base.with_changes(**{name: value for name, value in flags.items() if value is not None})


def _reuses(args: argparse.Namespace) -> bool:
    """Say whether the flags reuse a finished run instead of asking for a new story."""
    return bool(args.plan_from or args.narrate_from)


def read_request(args: argparse.Namespace) -> StoryBrief | str:
    """Return the brief the flags point at, or the prompt given or typed in."""
    if _reuses(args):
        return ""
    if args.brief:
        return StoryBrief.model_validate_json(args.brief.read_text(encoding="utf-8"))
    if args.prompt_file:
        return args.prompt_file.read_text(encoding="utf-8-sig").strip()
    return (args.prompt or input("Describe la historia que quieres generar:\n> ")).strip()


def apply_setting_flags(args: argparse.Namespace, settings):
    """Let --model, --stage-model and --output outrank .env for this run only."""
    flags = {"model": args.model, "stage_model": args.stage_model, "output_root": args.output}
    return replace(settings, **{name: value for name, value in flags.items() if value})


def request_problem(
    args: argparse.Namespace, options: GenerationOptions, prompt: StoryBrief | str
) -> str | None:
    """Say why a run cannot start from these flags and this request, or None when it can."""
    if args.plan_from and args.narrate_from:
        return "usa --plan-from o --narrate-from, no los dos."
    if args.plan_from and options.story_format is StoryFormat.SCRIPT:
        return "--plan-from exige --format simulated o narrative."
    if args.narrate_from and options.story_format is not StoryFormat.SIMULATED:
        return "--narrate-from exige --format simulated."
    if not prompt and not _reuses(args):
        return "el prompt no puede estar vacío."
    return None


def print_banner(args: argparse.Namespace) -> None:
    """Greet, and show the example prompt only when one is about to be typed in."""
    print("Generador automático de historias — Stagecraft")
    if not (args.prompt or args.prompt_file or args.brief or _reuses(args)):
        print("\nEjemplo de prompt ideal:\n")
        print(f"  {EXAMPLE_PROMPT}\n")


def run(generator: StoryGenerator, args: argparse.Namespace, prompt: StoryBrief | str):
    """Generate the story the flags ask for: a new one, or a replay of a finished run."""

    def report_progress(update) -> None:
        """Print one formatted pipeline progress update."""
        print(format_progress(update), flush=True)

    def report_event(event) -> None:
        """Print one structured pipeline event message."""
        print(event.message, flush=True)

    callbacks = {"on_progress": report_progress, "on_event": report_event}
    if args.narrate_from:
        return generator.generate_from_performance(args.narrate_from, **callbacks)
    if args.plan_from:
        return generator.generate_from_plan(args.plan_from, **callbacks)
    return generator.generate(prompt, **callbacks)


def main(argv: list[str] | None = None) -> int:
    """Run the command-line entry point."""
    use_utf8_output()
    args = parser().parse_args(argv)
    print_banner(args)
    given = [item for item in (args.prompt, args.prompt_file, args.brief) if item]
    if len(given) > 1 or (_reuses(args) and given):
        print("Error: usa un prompt, --prompt-file o --brief, solo uno.", file=sys.stderr)
        return 2
    try:
        try:
            prompt = read_request(args)
            settings = load_settings()
            options = build_options(args, settings)
        except (OSError, ValidationError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        problem = request_problem(args, options, prompt)
        if problem:
            print(f"Error: {problem}", file=sys.stderr)
            return 2
        settings = apply_setting_flags(args, settings)
        # A narration replay costs about what a narrative run does, not a whole performance.
        budgeted = "narrative" if args.narrate_from else options.story_format.value
        refusal = None if args.force else preflight(settings, budgeted)
        if refusal:
            print(f"Error: no cabe en la cuota de hoy: {refusal}", file=sys.stderr)
            return 3
        provider = provider_from_settings(settings)
        generator = StoryGenerator.from_options(provider, settings.output_root, options)

        simulated = options.story_format is StoryFormat.SIMULATED
        print(f"\nGenerando con {settings.model_summary(simulated=simulated)}...")
        output = run(generator, args, prompt)
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
    except (ASGError, OSError, ValueError, KeyboardInterrupt) as exc:
        message = exc.public_message() if isinstance(exc, ASGError) else "operación cancelada"
        print(f"\nError: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
