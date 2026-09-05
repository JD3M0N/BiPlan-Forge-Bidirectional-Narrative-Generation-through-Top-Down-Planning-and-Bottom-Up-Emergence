import json
from types import SimpleNamespace

import asg_top_down.provider as provider_module
import pytest
from asg_top_down.errors import (
    EmptyResponseError,
    GeminiDailyQuotaError,
    ProviderError,
    StructuredResponseError,
)
from asg_top_down.provider import GeminiProvider, _gemini_response_schema
from asg_top_down.schemas import StoryRequest


class FakeModels:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.count_calls = 0
        self.generate_calls = []

    def generate_content(self, **kwargs):
        self.generate_calls.append(kwargs)
        if self.error:
            raise self.error
        if isinstance(self.response, list):
            return self.response.pop(0)
        return self.response

    def count_tokens(self, **kwargs):
        self.count_calls += 1
        return SimpleNamespace(total_tokens=42)


def provider_with(response=None, error: Exception | None = None) -> GeminiProvider:
    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model_name = "fake-flash"
    provider._client = SimpleNamespace(models=FakeModels(response, error))
    return provider


def test_gemini_schema_omits_unsupported_additional_properties() -> None:
    schema = _gemini_response_schema(StoryRequest)

    def contains_additional_properties(value) -> bool:
        if isinstance(value, dict):
            return "additionalProperties" in value or any(
                contains_additional_properties(item) for item in value.values()
            )
        if isinstance(value, list):
            return any(contains_additional_properties(item) for item in value)
        return False

    assert not contains_additional_properties(schema)
    assert schema["properties"]["narrative_profile"]["$ref"] == "#/$defs/NarrativeProfile"


def test_structured_generation_rejects_invalid_json() -> None:
    provider = provider_with(SimpleNamespace(parsed=None, text="{invalid"))
    with pytest.raises(StructuredResponseError):
        provider.generate_structured(
            system_instruction="test", prompt="test", schema=StoryRequest, profile="extraction"
        )


def test_structured_generation_retries_validation_once_then_succeeds() -> None:
    valid = StoryRequest(
        original_prompt="historia",
        title="Título",
        genre="fantasía",
        tone="tenso",
        narrative_profile="developed",
        premise="Una promesa",
    ).model_dump_json()
    provider = provider_with(
        [
            SimpleNamespace(parsed=None, text="{invalid"),
            SimpleNamespace(parsed=None, text=valid),
        ]
    )
    result = provider.generate_structured(
        system_instruction="test",
        prompt="PRIVATE PROMPT",
        schema=StoryRequest,
        profile="extraction",
    )
    assert result.title == "Título"
    assert len(provider._client.models.generate_calls) == 2
    correction = provider._client.models.generate_calls[1]["contents"]
    assert "json_invalid" in correction
    assert "{invalid" not in correction


def test_structured_generation_reports_sanitized_errors_after_retry() -> None:
    provider = provider_with(
        [
            SimpleNamespace(parsed=None, text="{}"),
            SimpleNamespace(parsed=None, text="{}"),
        ]
    )
    with pytest.raises(StructuredResponseError) as captured:
        provider.generate_structured(
            system_instruction="test",
            prompt="PRIVATE PROMPT",
            schema=StoryRequest,
            profile="extraction",
        )
    details = captured.value.details
    assert details["schema"] == "StoryRequest"
    assert details["attempts"] == 2
    assert {item["location"] for item in details["validation_errors"]} >= {
        "original_prompt",
        "title",
        "genre",
        "tone",
        "premise",
    }
    assert "PRIVATE PROMPT" not in json.dumps(details)


def test_structured_generation_rejects_empty_response() -> None:
    provider = provider_with(SimpleNamespace(parsed=None, text=""))
    with pytest.raises(EmptyResponseError):
        provider.generate_structured(
            system_instruction="test", prompt="test", schema=StoryRequest, profile="extraction"
        )


def test_text_generation_rejects_empty_response() -> None:
    provider = provider_with(SimpleNamespace(text="  "))
    with pytest.raises(EmptyResponseError):
        provider.generate_text(system_instruction="test", prompt="test", profile="prose")


def test_provider_wraps_transport_errors() -> None:
    provider = provider_with(error=OSError("sin red"))
    with pytest.raises(ProviderError, match="comunicarse con Gemini"):
        provider.generate_text(system_instruction="test", prompt="test", profile="prose")


def test_usage_metadata_is_recorded_without_count_tokens_by_default() -> None:
    response = SimpleNamespace(
        text="respuesta",
        usage_metadata=SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=5,
            thoughts_token_count=2,
            cached_content_token_count=1,
            total_token_count=17,
        ),
    )
    provider = provider_with(response)
    assert (
        provider.generate_text(system_instruction="test", prompt="test", profile="prose")
        == "respuesta"
    )
    assert provider._client.models.count_calls == 0
    assert provider.usage_records[0].total_tokens == 17


def test_usage_callback_receives_each_completed_call() -> None:
    provider = provider_with(SimpleNamespace(text="respuesta", usage_metadata=None))
    received = []
    provider.usage_callback = received.append
    provider.generate_text(system_instruction="test", prompt="test", profile="prose")
    assert received == provider.usage_records


def test_tpm_preflight_calls_count_tokens_only_when_configured() -> None:
    provider = provider_with(SimpleNamespace(text="respuesta", usage_metadata=None))
    acquired = []
    provider._token_limiter = SimpleNamespace(
        acquire=lambda tokens, callback: acquired.append(tokens)
    )
    provider.wait_callback = None
    provider.generate_text(system_instruction="sistema", prompt="texto", profile="prose")
    assert provider._client.models.count_calls == 1
    assert acquired == [42]


def test_daily_quota_is_not_retried() -> None:
    provider = provider_with(
        error=Exception("429 Quota exceeded for metric: requests_per_day, 'quotaId': 'PerDay'")
    )
    provider.max_retries = 3
    with pytest.raises(GeminiDailyQuotaError):
        provider._generate("text", provider._client.models.generate_content)


def test_connect_error_is_retried_then_succeeds(monkeypatch) -> None:
    class ConnectError(Exception):
        pass

    class FlakyModels(FakeModels):
        def generate_content(self, **kwargs):
            self.generate_calls.append(kwargs)
            if len(self.generate_calls) == 1:
                raise ConnectError("getaddrinfo failed")
            return SimpleNamespace(text="respuesta", usage_metadata=None)

    provider = provider_with()
    provider.max_retries = 3
    provider._client.models = FlakyModels()
    monkeypatch.setattr(provider_module, "retry_delay", lambda attempt, details: 0)
    monkeypatch.setattr(provider_module, "countdown_wait", lambda *args: None)
    assert (
        provider.generate_text(system_instruction="test", prompt="test", profile="prose")
        == "respuesta"
    )
    assert len(provider._client.models.generate_calls) == 2
    assert [record.status for record in provider.usage_records] == ["failed", "succeeded"]


def test_authentication_error_is_not_retried() -> None:
    provider = provider_with(error=Exception("401 invalid API key"))
    provider.max_retries = 3
    with pytest.raises(ProviderError):
        provider.generate_text(system_instruction="test", prompt="test", profile="prose")
    assert len(provider._client.models.generate_calls) == 1


def test_socket_permission_error_is_classified_as_transport() -> None:
    class ConnectError(Exception):
        pass

    error = provider_module._safe_provider_error(
        ConnectError("socket access forbidden by its access permissions")
    )
    assert "comunicarse con Gemini" in error.summary


def test_client_error_preserves_safe_status_diagnostics() -> None:
    class ClientError(Exception):
        code = 400
        status = "INVALID_ARGUMENT"

    error = provider_module._safe_provider_error(ClientError("400 invalid argument"))
    assert error.details["status"] == 400
    assert error.details["status_name"] == "INVALID_ARGUMENT"
    assert "esquema" in error.summary


def test_temperature_uses_explicit_profile_for_structured_generation() -> None:
    valid = StoryRequest(
        original_prompt="historia",
        title="Título",
        genre="fantasía",
        tone="tenso",
        narrative_profile="developed",
        premise="Una promesa",
    ).model_dump_json()
    provider = provider_with(SimpleNamespace(parsed=None, text=valid))
    provider.generate_structured(
        system_instruction="test", prompt="test", schema=StoryRequest, profile="extraction"
    )
    config = provider._client.models.generate_calls[-1]["config"]
    assert config.temperature == 0.15


def test_temperature_uses_explicit_profile_for_text_generation() -> None:
    provider = provider_with(SimpleNamespace(text="respuesta", usage_metadata=None))
    provider.generate_text(system_instruction="test", prompt="test", profile="rewrite")
    config = provider._client.models.generate_calls[-1]["config"]
    assert config.temperature == 0.35


def test_temperature_rejects_unknown_profile() -> None:
    provider = provider_with(SimpleNamespace(text="respuesta", usage_metadata=None))
    with pytest.raises(ValueError, match="not-a-real-profile"):
        provider.generate_text(
            system_instruction="test", prompt="test", profile="not-a-real-profile"
        )


def test_generation_profiles_override_merges_with_defaults() -> None:
    provider = provider_with()
    provider.generation_profiles = {
        **provider_module._DEFAULT_GENERATION_PROFILES,
        "prose": 1.0,
    }
    assert provider._temperature("prose") == 1.0
    assert provider._temperature("review") == provider_module._DEFAULT_GENERATION_PROFILES["review"]
