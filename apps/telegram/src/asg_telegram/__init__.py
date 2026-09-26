"""Public API for the ASG Telegram interface."""

from .contract import StoryGeneratorAdapter
from .generators import (
    GeneratorRegistry,
    StagecraftGenerator,
    create_generator,
)

__all__ = [
    "GeneratorRegistry",
    "StoryGeneratorAdapter",
    "StagecraftGenerator",
    "create_generator",
]
