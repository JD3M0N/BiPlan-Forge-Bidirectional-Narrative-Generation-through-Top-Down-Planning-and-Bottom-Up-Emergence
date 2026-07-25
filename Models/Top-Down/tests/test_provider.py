from types import SimpleNamespace

import pytest

from asg_top_down.errors import EmptyResponseError, ProviderError, StructuredResponseError
from asg_top_down.provider import GeminiProvider
from asg_top_down.schemas import StoryRequest


class FakeModels:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    def generate_content(self, **kwargs):
        if self.error:
            raise self.error
        return self.response


def provider_with(response=None, error: Exception | None = None) -> GeminiProvider:
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model_name = "fake-flash"
    provider._client = SimpleNamespace(models=FakeModels(response, error))
    return provider


def test_structured_generation_rejects_invalid_json() -> None:
    provider = provider_with(SimpleNamespace(parsed=None, text="{invalid"))
    with pytest.raises(StructuredResponseError):
        provider.generate_structured(
            system_instruction="test", prompt="test", schema=StoryRequest
        )


def test_structured_generation_rejects_empty_response() -> None:
    provider = provider_with(SimpleNamespace(parsed=None, text=""))
    with pytest.raises(EmptyResponseError):
        provider.generate_structured(
            system_instruction="test", prompt="test", schema=StoryRequest
        )


def test_text_generation_rejects_empty_response() -> None:
    provider = provider_with(SimpleNamespace(text="  "))
    with pytest.raises(EmptyResponseError):
        provider.generate_text(system_instruction="test", prompt="test")


def test_provider_wraps_transport_errors() -> None:
    provider = provider_with(error=OSError("sin red"))
    with pytest.raises(ProviderError, match="sin red"):
        provider.generate_text(system_instruction="test", prompt="test")

