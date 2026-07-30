"""Abstracción intercambiable de los enfoques de generación."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from asg_top_down.config import load_settings as load_top_down_settings
from asg_top_down.orchestrator import StoryOrchestrator
from asg_top_down.provider import GeminiProvider


class StoryGenerator(Protocol):
    @property
    def display_name(self) -> str: ...

    def generate(self, prompt: str) -> Path: ...


class TopDownGenerator:
    @property
    def display_name(self) -> str:
        return "Top-Down"

    def generate(self, prompt: str) -> Path:
        settings = load_top_down_settings()
        provider = GeminiProvider(settings.api_key, settings.model)
        return StoryOrchestrator(provider, settings.output_root).run(prompt)


GeneratorFactory = Callable[[], StoryGenerator]


class GeneratorRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, GeneratorFactory] = {}

    def register(self, name: str, factory: GeneratorFactory) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("El nombre del generador no puede estar vacío.")
        self._factories[normalized] = factory

    @property
    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def create(self, name: str) -> StoryGenerator:
        normalized = name.strip().lower()
        try:
            return self._factories[normalized]()
        except KeyError as exc:
            choices = ", ".join(self.available) or "ninguno"
            raise ValueError(
                f"Generador desconocido '{name}'. Disponibles: {choices}."
            ) from exc


DEFAULT_REGISTRY = GeneratorRegistry()
DEFAULT_REGISTRY.register("top-down", TopDownGenerator)


def create_generator(
    name: str, registry: GeneratorRegistry = DEFAULT_REGISTRY
) -> StoryGenerator:
    return registry.create(name)
