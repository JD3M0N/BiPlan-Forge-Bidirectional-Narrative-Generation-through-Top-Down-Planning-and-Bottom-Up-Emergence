"""Interactive menu for Top-Down story generation."""

from __future__ import annotations

from asg_top_down import StoryGenerator
from asg_top_down.config import load_settings as load_top_down_settings
from asg_top_down.formats import OUTPUT_CHOICES, output_choice
from asg_top_down.progress import format_progress
from asg_top_down.provider import provider_from_settings

from .types import InputFn, OutputFn


class TopDownMenu:
    """Collect a prompt and run the configured Top-Down generator."""

    def __init__(self, input_fn: InputFn = input, output: OutputFn = print) -> None:
        """Configure console input and output functions."""
        self.input = input_fn
        self.output = output

    def run(self) -> None:
        """Display the Top-Down menu until the user returns."""
        while True:
            self.output("\nTop-Down\n  1. Generate story\n  0. Volver")
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
        settings = load_top_down_settings()
        provider = provider_from_settings(settings)
        choice = self._choose_output(settings)
        self.output(f"Generando con {settings.model}...")
        generator = StoryGenerator(
            provider,
            settings.output_root,
            narrative_guidance=settings.narrative_guidance,
            promise_ledger=settings.promise_ledger,
            story_format=choice.story_format,
            script_method=choice.script_method,
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
        if choice.story_format.value == "script":
            self.output(f"Guion terminado: {output_dir / 'story.md'}")
            self.output(f"Guion estructurado: {output_dir / 'script.json'}")
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
