"""Agentes especializados del pipeline Top-Down."""

import json
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from .provider import LanguageModelProvider
from .schemas import (
    CharactersArtifact,
    OutlineArtifact,
    ReviewArtifact,
    StoryRequest,
    WorldArtifact,
)

T = TypeVar("T")


def _json(value: BaseModel) -> str:
    return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2)


class Agent(ABC, Generic[T]):
    name: str

    def __init__(self, provider: LanguageModelProvider) -> None:
        self.provider = provider

    @abstractmethod
    def run(self, *args: object, **kwargs: object) -> T:
        """Produce el artefacto propio del agente."""


class AnalystAgent(Agent[StoryRequest]):
    name = "analyst"

    def run(self, prompt: str) -> StoryRequest:
        return self.provider.generate_structured(
            system_instruction=(
                "Eres analista de requisitos narrativos. Convierte la petición en "
                "una especificación fiel. Si no indica idioma usa español; si no "
                "indica extensión usa 1500 palabras. No inventes restricciones."
            ),
            prompt=prompt,
            schema=StoryRequest,
        )


class WorldBuilderAgent(Agent[WorldArtifact]):
    name = "world"

    def run(self, request: StoryRequest) -> WorldArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Eres diseñador de mundos. Define solo elementos que sostengan la "
                "premisa, el tono y el conflicto; mantén reglas consistentes."
            ),
            prompt=_json(request),
            schema=WorldArtifact,
        )


class CharacterDesignerAgent(Agent[CharactersArtifact]):
    name = "characters"

    def run(
        self, request: StoryRequest, world: WorldArtifact
    ) -> CharactersArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Eres diseñador de personajes. Crea un reparto compacto con deseos, "
                "conflictos y arcos conectados a la premisa y al mundo."
            ),
            prompt=f"REQUISITOS:\n{_json(request)}\n\nMUNDO:\n{_json(world)}",
            schema=CharactersArtifact,
        )


class PlotArchitectAgent(Agent[OutlineArtifact]):
    name = "outline"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
    ) -> OutlineArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Eres arquitecto narrativo Top-Down. Diseña una secuencia causal "
                "completa con planteamiento, escalada, clímax y resolución."
            ),
            prompt=(
                f"REQUISITOS:\n{_json(request)}\n\nMUNDO:\n{_json(world)}"
                f"\n\nPERSONAJES:\n{_json(characters)}"
            ),
            schema=OutlineArtifact,
        )


class WriterAgent(Agent[str]):
    name = "draft"

    def run(
        self,
        request: StoryRequest,
        world: WorldArtifact,
        characters: CharactersArtifact,
        outline: OutlineArtifact,
    ) -> str:
        return self.provider.generate_text(
            system_instruction=(
                "Eres un escritor de ficción. Redacta una historia completa en "
                "Markdown, sin comentarios sobre el proceso. Respeta estrictamente "
                "el idioma, la extensión aproximada y el esquema."
            ),
            prompt=(
                f"REQUISITOS:\n{_json(request)}\n\nMUNDO:\n{_json(world)}"
                f"\n\nPERSONAJES:\n{_json(characters)}"
                f"\n\nESQUEMA:\n{_json(outline)}"
            ),
        )


class CriticAgent(Agent[ReviewArtifact]):
    name = "review"

    def run(
        self,
        request: StoryRequest,
        outline: OutlineArtifact,
        draft: str,
    ) -> ReviewArtifact:
        return self.provider.generate_structured(
            system_instruction=(
                "Eres un crítico editorial riguroso. Evalúa coherencia, continuidad, "
                "estilo y cumplimiento. Da instrucciones de revisión concretas."
            ),
            prompt=(
                f"REQUISITOS:\n{_json(request)}\n\nESQUEMA:\n{_json(outline)}"
                f"\n\nBORRADOR:\n{draft}"
            ),
            schema=ReviewArtifact,
        )


class EditorAgent(Agent[str]):
    name = "story"

    def run(
        self,
        request: StoryRequest,
        outline: OutlineArtifact,
        draft: str,
        review: ReviewArtifact,
    ) -> str:
        return self.provider.generate_text(
            system_instruction=(
                "Eres editor literario. Reescribe una sola vez el borrador aplicando "
                "la crítica. Devuelve únicamente la historia final completa en "
                "Markdown, sin notas editoriales."
            ),
            prompt=(
                f"REQUISITOS:\n{_json(request)}\n\nESQUEMA:\n{_json(outline)}"
                f"\n\nCRÍTICA:\n{_json(review)}\n\nBORRADOR:\n{draft}"
            ),
        )

