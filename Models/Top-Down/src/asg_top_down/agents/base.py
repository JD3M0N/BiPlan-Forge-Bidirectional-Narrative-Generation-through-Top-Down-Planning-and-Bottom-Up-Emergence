"""Shared agent infrastructure."""

import json
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

from ..provider import LanguageModelProvider

T = TypeVar("T")


def json_text(value: BaseModel | list[BaseModel]) -> str:
    payload = [item.model_dump(mode="json") for item in value] if isinstance(value, list) else value.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, indent=2)


class Agent(ABC, Generic[T]):
    name: str

    def __init__(self, provider: LanguageModelProvider) -> None:
        self.provider = provider

    @abstractmethod
    def run(self, *args: object, **kwargs: object) -> T:
        """Produce the artifact owned by this agent."""
