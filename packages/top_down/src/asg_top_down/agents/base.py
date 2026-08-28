"""Shared agent infrastructure."""

import json
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from ..provider import LanguageModelProvider

T = TypeVar("T")


def json_text(value: Any) -> str:
    """Handle the json text operation for component."""

    def convert(item: Any) -> Any:
        """Handle the convert operation for component."""
        if isinstance(item, BaseModel):
            return item.model_dump(mode="json")
        if isinstance(item, dict):
            return {key: convert(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(child) for child in item]
        return item

    return json.dumps(convert(value), ensure_ascii=False, indent=2)


class Agent(ABC, Generic[T]):
    """Represent Agent data and behavior."""

    name: str

    def __init__(self, provider: LanguageModelProvider) -> None:
        """Initialize the Agent instance."""
        self.provider = provider

    @abstractmethod
    def run(self, *args: object, **kwargs: object) -> T:
        """Produce the artifact owned by this agent."""
