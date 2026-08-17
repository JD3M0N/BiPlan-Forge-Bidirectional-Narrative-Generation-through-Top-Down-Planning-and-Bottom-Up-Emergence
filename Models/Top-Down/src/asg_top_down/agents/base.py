"""Shared agent infrastructure."""

import json
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from ..provider import LanguageModelProvider

T = TypeVar("T")


def json_text(value: Any) -> str:
    def convert(item: Any) -> Any:
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, dict):
            return {key: convert(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(child) for child in item]
        return item

    return json.dumps(convert(value), ensure_ascii=False, indent=2)


class Agent(ABC, Generic[T]):
    name: str

    def __init__(self, provider: LanguageModelProvider) -> None:
        self.provider = provider

    @abstractmethod
    def run(self, *args: object, **kwargs: object) -> T:
        """Produce the artifact owned by this agent."""
