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


def valid_story_request_json() -> str:
    return StoryRequest(
        original_prompt="historia",
        title="Título",
        genre="fantasía",
        tone="tenso",
        narrative_profile="developed",
        premise="Una promesa",
    ).model_dump_json()


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


@pytest.mark.parametrize(
    "call",
    [
        lambda provider: provider.generate_structured(
            system_instruction="test", prompt="test", schema=StoryRequest, profile="extraction"
        ),
        lambda provider: provider.generate_text(
            system_instruction="test", prompt="test", profile="prose"
        ),
    ],
    ids=["structured", "text"],
)
def test_empty_responses_are_rejected(call) -> None:
    provider = provider_with(SimpleNamespace(parsed=None, text=""))
    with pytest.raises(EmptyResponseError):
        call(provider)


def test_structured_generation_rejects_invalid_json() -> None:
    provider = provider_with(SimpleNamespace(parsed=None, text="{invalid"))
    with pytest.raises(StructuredResponseError):
        provider.generate_structured(
            system_instruction="test", prompt="test", schema=StoryRequest, profile="extraction"
        )


def test_structured_generation_retries_validation_once_then_succeeds() -> None:
    provider = provider_with(
        [
            SimpleNamespace(parsed=None, text="{invalid"),
            SimpleNamespace(parsed=None, text=valid_story_request_json()),
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


def test_provider_wraps_transport_errors() -> None:
    provider = provider_with(error=OSError("sin red"))
    with pytest.raises(ProviderError, match="comunicarse con Gemini"):
        provider.generate_text(system_instruction="test", prompt="test", profile="prose")


@pytest.mark.parametrize(
    ("configure_limiter", "expected_count_calls"),
    [(False, 0), (True, 1)],
    ids=["no-tpm-limiter", "tpm-limiter-configured"],
)
def test_usage_metadata_respects_tpm_preflight_configuration(
    configure_limiter, expected_count_calls
) -> None:
    """count_tokens only runs when a token-window limiter is actually configured."""
    provider = provider_with(
        SimpleNamespace(
            text="respuesta",
            usage_metadata=SimpleNamespace(
                prompt_token_count=10,
                candidates_token_count=5,
                thoughts_token_count=2,
                cached_content_token_count=1,
                total_token_count=17,
            ),
        )
    )
    if configure_limiter:
        acquired = []
        provider._token_limiter = SimpleNamespace(
            acquire=lambda tokens, callback: acquired.append(tokens)
        )
        provider.wait_callback = None
    assert (
        provider.generate_text(system_instruction="test", prompt="test", profile="prose")
        == "respuesta"
    )
    assert provider._client.models.count_calls == expected_count_calls
    if not configure_limiter:
        assert provider.usage_records[0].total_tokens == 17


@pytest.mark.parametrize(
    ("error_text", "expected_exception", "call"),
    [
        (
            "429 Quota exceeded for metric: requests_per_day, 'quotaId': 'PerDay'",
            GeminiDailyQuotaError,
            lambda provider: provider._generate("text", provider._client.models.generate_content),
        ),
        (
            "401 invalid API key",
            ProviderError,
            lambda provider: provider.generate_text(
                system_instruction="test", prompt="test", profile="prose"
            ),
        ),
    ],
    ids=["daily-quota-not-retried", "authentication-error-not-retried"],
)
def test_non_retryable_errors_fail_immediately(error_text, expected_exception, call) -> None:
    provider = provider_with(error=Exception(error_text))
    provider.max_retries = 3
    with pytest.raises(expected_exception):
        call(provider)
    assert len(provider._client.models.generate_calls) == 1


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


@pytest.mark.parametrize(
    ("build_error", "assertions"),
    [
        (
            lambda: type("ConnectError", (Exception,), {})(
                "socket access forbidden by its access permissions"
            ),
            lambda error: "comunicarse con Gemini" in error.summary,
        ),
        (
            lambda: type("ClientError", (Exception,), {"code": 400, "status": "INVALID_ARGUMENT"})(
                "400 invalid argument"
            ),
            lambda error: (
                error.details["status"] == 400
                and error.details["status_name"] == "INVALID_ARGUMENT"
                and "esquema" in error.summary
            ),
        ),
    ],
    ids=["socket-permission-is-transport", "client-error-preserves-status-diagnostics"],
)
def test_error_classification_preserves_safe_diagnostics(build_error, assertions) -> None:
    error = provider_module._safe_provider_error(build_error())
    assert assertions(error)


@pytest.mark.parametrize(
    ("call", "profile", "expected_temperature"),
    [
        (
            lambda provider: provider.generate_structured(
                system_instruction="test",
                prompt="test",
                schema=StoryRequest,
                profile="extraction",
            ),
            None,
            0.15,
        ),
        (
            lambda provider: provider.generate_text(
                system_instruction="test", prompt="test", profile="rewrite"
            ),
            None,
            0.35,
        ),
    ],
    ids=["structured-extraction-profile", "text-rewrite-profile"],
)
def test_temperature_uses_the_explicit_profile(call, profile, expected_temperature) -> None:
    provider = provider_with(SimpleNamespace(parsed=None, text=valid_story_request_json()))
    call(provider)
    config = provider._client.models.generate_calls[-1]["config"]
    assert config.temperature == expected_temperature


def test_unknown_temperature_profile_is_rejected_and_overrides_merge_with_defaults() -> None:
    """An unknown profile name fails fast, and an explicit override only replaces its entry."""
    provider = provider_with(SimpleNamespace(text="respuesta", usage_metadata=None))
    with pytest.raises(ValueError, match="not-a-real-profile"):
        provider.generate_text(
            system_instruction="test", prompt="test", profile="not-a-real-profile"
        )
    provider.generation_profiles = {
        **provider_module._DEFAULT_GENERATION_PROFILES,
        "prose": 1.0,
    }
    assert provider._temperature("prose") == 1.0
    assert provider._temperature("review") == provider_module._DEFAULT_GENERATION_PROFILES["review"]
