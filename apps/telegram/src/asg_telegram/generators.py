"""Interchangeable adapters for story-generation approaches."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from asg_top_down import StoryGenerator
from asg_top_down.config import load_settings as load_top_down_settings
from asg_top_down.progress import PipelineEventCallback, ProgressCallback
from asg_top_down.provider import provider_from_settings


class StoryGeneratorAdapter(Protocol):
    """Define the interchangeable story-generator adapter contract."""

    @property
    def display_name(self) -> str:
        """Return the generator name shown to Telegram users."""
        ...

    def generate(
        self,
        prompt: str,
        on_progress: ProgressCallback | None = None,
        on_run_created=None,
        on_event: PipelineEventCallback | None = None,
    ) -> Path:
        """Generate one story and return its run directory."""
        ...


class TopDownGenerator:
    """Adapt the Top-Down generator to the Telegram interface."""

    @property
    def display_name(self) -> str:
        """Handle the display name operation for TopDownGenerator."""
        return "Top-Down"

    def generate(
        self,
        prompt: str,
        on_progress: ProgressCallback | None = None,
        on_run_created=None,
        on_event: PipelineEventCallback | None = None,
    ) -> Path:
        """Generate the requested value."""
        settings = load_top_down_settings()
        provider = provider_from_settings(settings)
        return (
            StoryGenerator(
                provider,
                settings.output_root,
            )
            .run(
                prompt,
                on_progress=on_progress,
                on_run_created=on_run_created,
                on_event=on_event,
            )
            .run_dir
        )


GeneratorFactory = Callable[[], StoryGeneratorAdapter]


class GeneratorRegistry:
    """Represent GeneratorRegistry data and behavior."""

    def __init__(self) -> None:
        """Initialize the GeneratorRegistry instance."""
        self._factories: dict[str, GeneratorFactory] = {}

    def register(self, name: str, factory: GeneratorFactory) -> None:
        """Register the requested value."""
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("El nombre del generador no puede estar vacío.")
        self._factories[normalized] = factory

    @property
    def available(self) -> tuple[str, ...]:
        """Handle the available operation for GeneratorRegistry."""
        return tuple(sorted(self._factories))

    def create(self, name: str) -> StoryGeneratorAdapter:
        """Create the requested value."""
        normalized = name.strip().lower()
        try:
            return self._factories[normalized]()
        except KeyError as exc:
            choices = ", ".join(self.available) or "ninguno"
            raise ValueError(f"Generador desconocido '{name}'. Disponibles: {choices}.") from exc


DEFAULT_REGISTRY = GeneratorRegistry()
DEFAULT_REGISTRY.register("top-down", TopDownGenerator)


def create_generator(
    name: str, registry: GeneratorRegistry = DEFAULT_REGISTRY
) -> StoryGeneratorAdapter:
    """Create generator."""
    return registry.create(name)
