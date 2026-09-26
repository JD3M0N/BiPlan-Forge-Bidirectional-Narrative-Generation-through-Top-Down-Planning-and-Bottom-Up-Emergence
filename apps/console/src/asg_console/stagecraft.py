"""Interactive menu for Stagecraft story generation."""

from __future__ import annotations

from asg_stagecraft import StoryGenerator
from asg_stagecraft.formats import (
    OUTPUT_CHOICES,
    NarrativeVoice,
    StoryFormat,
    output_choice,
)
from asg_stagecraft.runtime.config import load_settings as load_stagecraft_settings
from asg_stagecraft.runtime.progress import format_progress
from asg_stagecraft.runtime.provider import provider_from_settings

from .types import InputFn, OutputFn


class StagecraftMenu:
    """Collect a prompt and run the configured Stagecraft generator."""

    def __init__(self, input_fn: InputFn = input, output: OutputFn = print) -> None:
        """Configure console input and output functions."""
        self.input = input_fn
        self.output = output

    def run(self) -> None:
        """Display the Stagecraft menu until the user returns."""
        while True:
            self.output("\nStagecraft\n  1. Generate story\n  0. Volver")
            choice = self.input("> ").strip()
            if choice == "0":
                return
            if choice != "1":
                self.output("Opción inválida.")
                continue
            prompt = self.input("Describe la historia:\n> ").strip()
            if not prompt:
                self.output("El prompt no puede estar vacío.")
                continue
            self._generate(prompt)

    def _generate(self, prompt: str) -> None:
        """Build runtime dependencies and generate one requested story."""
        settings = load_stagecraft_settings()
        provider = provider_from_settings(settings)
        choice = self._choose_output(settings)
        voice = (
            self._choose_voice(settings)
            if choice.story_format is StoryFormat.SIMULATED
            else settings.narrative_voice
        )
        self.output(f"Generando con {settings.model}...")
        generator = StoryGenerator(
            provider,
            settings.output_root,
            narrative_guidance=settings.narrative_guidance,
            promise_ledger=settings.promise_ledger,
            story_format=choice.story_format,
            script_method=choice.script_method,
            narrative_voice=voice,
            actor_memory=settings.actor_memory,
            turns_per_beat=settings.turns_per_beat,
        )

        def report_progress(update) -> None:
            """Write one formatted pipeline progress update to the console."""
            self.output(format_progress(update))

        def report_event(event) -> None:
            """Write one structured pipeline event to the console."""
            self.output(event.message)

        output = generator.generate(
            prompt,
            on_progress=report_progress,
            on_event=report_event,
        )
        output_dir = output.run_dir if hasattr(output, "run_dir") else output
        if choice.story_format is StoryFormat.SCRIPT:
            self.output(f"Guion terminado: {output_dir / 'story.md'}")
            self.output(f"Guion estructurado: {output_dir / 'script.json'}")
        elif choice.story_format is StoryFormat.SIMULATED:
            self.output(f"Historia simulada terminada: {output_dir / 'story.md'}")
            self.output(f"Funcion representada: {output_dir / 'performance.md'}")
        else:
            self.output(f"Historia terminada: {output_dir / 'story.md'}")
        audio_path = output_dir / "story.mp3"
        if audio_path.is_file():
            self.output(f"Audio disponible en: {audio_path}")
        else:
            self.output("La historia se guardó, pero no fue posible crear el audio.")

    def _choose_output(self, settings):
        """Prompt for one of the combined output choices, keeping the settings default."""
        default = output_choice(settings.story_format, settings.script_method)
        options = "\n".join(
            f"  {index}. {item.label}" for index, item in enumerate(OUTPUT_CHOICES, 1)
        )
        default_index = OUTPUT_CHOICES.index(default) + 1
        while True:
            self.output(f"\nFormato de salida:\n{options}")
            value = self.input(f"Formato [{default_index}]: ").strip()
            if not value:
                return default
            if value.isdigit() and 1 <= int(value) <= len(OUTPUT_CHOICES):
                return OUTPUT_CHOICES[int(value) - 1]
            self.output("Opción inválida.")

    def _choose_voice(self, settings):
        """Prompt for the point of view a simulated run narrates from."""
        options = list(NarrativeVoice)
        labels = {
            NarrativeVoice.OMNISCIENT: "Tercera persona omnisciente",
            NarrativeVoice.FOCALIZED: "Tercera persona focalizada por escena",
            NarrativeVoice.FIRST_PERSON: "Primera persona del protagonista",
        }
        listing = "\n".join(f"  {index}. {labels[item]}" for index, item in enumerate(options, 1))
        default_index = options.index(settings.narrative_voice) + 1
        while True:
            self.output(f"\nPunto de vista:\n{listing}")
            value = self.input(f"Punto de vista [{default_index}]: ").strip()
            if not value:
                return settings.narrative_voice
            if value.isdigit() and 1 <= int(value) <= len(options):
                return options[int(value) - 1]
            self.output("Opción inválida.")
