import json
from types import SimpleNamespace

import asg_stagecraft.runtime.provider as provider_module
import pytest
from asg_stagecraft.runtime.errors import (
    EmptyResponseError,
    GeminiBillingQuotaError,
    GeminiDailyQuotaError,
    ProviderError,
    StructuredResponseError,
)
from asg_stagecraft.runtime.provider import GeminiProvider, _gemini_response_schema
from asg_stagecraft.schemas import StoryRequest

# The 429 body Gemini returned in the three corpus runs filed as billing limits: its text asks
# to check "plan and billing details", but its quota ID is the free tier's daily request cap.
FREE_TIER_DAILY_429 = (
    "429 RESOURCE_EXHAUSTED. You exceeded your current quota, please check your plan and "
    "billing details. Quota exceeded for metric: "
    "generativelanguage.googleapis.com/generate_content_free_tier_requests, "
    "'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'"
)


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


def test_the_free_tier_daily_quota_is_not_mistaken_for_billing() -> None:
    """MED-1: reading the text before the quota ID turned three daily quotas into billing."""
    provider = provider_with(error=Exception(FREE_TIER_DAILY_429))
    with pytest.raises(GeminiDailyQuotaError) as raised:
        provider._generate("text", provider._client.models.generate_content)
    assert raised.value.details["quota_id"] == "GenerateRequestsPerDayPerProjectPerModel-FreeTier"


def test_the_attempts_of_one_call_share_its_id_and_keep_their_own_latency(monkeypatch) -> None:
    """MED-2: every attempt had its own call_id and a duration that added up the earlier ones."""

    class FlakyModels(FakeModels):
        def generate_content(self, **kwargs):
            self.generate_calls.append(kwargs)
            if len(self.generate_calls) == 1:
                raise type("ConnectError", (Exception,), {})("getaddrinfo failed")
            return SimpleNamespace(text="respuesta", usage_metadata=None)

    clock = iter([0.0, 3.0, 100.0, 104.0])
    provider = provider_with()
    provider.max_retries = 3
    provider._client.models = FlakyModels()
    monkeypatch.setattr(provider_module, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(provider_module, "retry_delay", lambda attempt, details: 5)
    monkeypatch.setattr(provider_module, "countdown_wait", lambda *args: None)
    provider._generate("text", provider._client.models.generate_content)
    records = provider.usage_records
    assert len({item.call_id for item in records}) == 1
    assert [item.attempt for item in records] == [1, 2]
    assert [item.duration_seconds for item in records] == [3.0, 4.0]
    assert [item.wait_seconds for item in records] == [0.0, 5]


def test_a_call_is_tagged_with_the_stage_and_agent_that_made_it() -> None:
    """MED-2: the stage field repeated the operation, so cost could not be split by agent."""
    provider = provider_with(response=SimpleNamespace(text="ok", usage_metadata=None))
    with provider_module.call_context("performance", "actor"):
        provider._generate("text", provider._client.models.generate_content)
    provider._generate("text", provider._client.models.generate_content)
    tagged, untagged = provider.usage_records
    assert (tagged.stage, tagged.agent) == ("performance", "actor")
    assert (untagged.stage, untagged.agent) == ("text", "")


def test_a_billing_limit_named_only_in_the_text_is_still_billing() -> None:
    provider = provider_with(error=Exception("429 Your spend cap was reached, check billing."))
    with pytest.raises(GeminiBillingQuotaError):
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


def test_unknown_temperature_profile_is_rejected() -> None:
    """An unknown profile name fails fast instead of silently borrowing another temperature."""
    provider = provider_with(SimpleNamespace(text="respuesta", usage_metadata=None))
    with pytest.raises(ValueError, match="not-a-real-profile"):
        provider.generate_text(
            system_instruction="test", prompt="test", profile="not-a-real-profile"
        )


def test_every_named_profile_resolves_to_its_documented_temperature() -> None:
    """The five named profiles are the only source of temperature, with no per-instance state."""
    provider = provider_with(SimpleNamespace(text="respuesta", usage_metadata=None))
    expected = {"extraction": 0.15, "review": 0.2, "planning": 0.5, "prose": 0.9, "rewrite": 0.35}
    assert provider_module._DEFAULT_GENERATION_PROFILES == expected
    for profile, temperature in expected.items():
        assert provider._temperature(profile) == temperature


def routed_pair() -> tuple[provider_module.RoutedProvider, GeminiProvider, GeminiProvider]:
    main = provider_with(response=SimpleNamespace(text="principal", usage_metadata=None))
    main.model_name = "main-model"
    stage = provider_with(response=SimpleNamespace(text="escena", usage_metadata=None))
    stage.model_name = "stage-model"
    return provider_module.RoutedProvider(main, stage), main, stage


def test_the_performance_goes_to_its_own_model_and_everything_else_to_the_main_one() -> None:
    routed, main, stage = routed_pair()
    ask = {"system_instruction": "s", "prompt": "p", "profile": "prose"}
    with provider_module.call_context("performance", "actor"):
        assert routed.generate_text(**ask) == "escena"
    with provider_module.call_context("performance", "stage_manager"):
        assert routed.generate_text(**ask) == "escena"
    for stage_name in ("planning", "casting", "narration"):
        with provider_module.call_context(stage_name, "agent"):
            assert routed.generate_text(**ask) == "principal"
    # A call outside any stage, such as the stage audit's judge, stays on the main model.
    assert routed.generate_text(**ask) == "principal"
    assert len(stage._client.models.generate_calls) == 2
    assert len(main._client.models.generate_calls) == 4
    assert [record.model for record in routed.usage_records] == [
        "stage-model",
        "stage-model",
        "main-model",
        "main-model",
        "main-model",
        "main-model",
    ]


def test_the_routed_pair_shares_one_usage_list_and_the_run_callbacks() -> None:
    routed, main, stage = routed_pair()
    seen, waits = [], []
    routed.usage_callback = seen.append
    routed.wait_callback = lambda seconds, reason: waits.append(reason)
    assert main.usage_callback is stage.usage_callback is routed.usage_callback
    assert main.wait_callback is stage.wait_callback is routed.wait_callback
    with provider_module.call_context("performance", "actor"):
        routed.generate_text(system_instruction="s", prompt="p", profile="prose")
    routed.generate_text(system_instruction="s", prompt="p", profile="prose")
    assert [record.model for record in seen] == ["stage-model", "main-model"]
    assert main.usage_records is stage.usage_records is routed.usage_records
    # The Telegram adapter empties the list between jobs; both providers must see it emptied.
    routed.usage_records.clear()
    assert main.usage_records == stage.usage_records == []
    routed.usage_callback = None
    assert main.usage_callback is None and stage.usage_callback is None
    assert routed.model_name == "main-model"
    assert routed.stage_model_name == "stage-model"


class RecordingGemini:
    """Stand in for GeminiProvider, keeping what the factory built it with."""

    built: list[dict] = []

    def __init__(self, api_key, model_name, **kwargs):
        self.model_name = model_name
        RecordingGemini.built.append({"api_key": api_key, "model": model_name, **kwargs})


def test_the_factory_builds_one_provider_until_the_performance_differs(monkeypatch, tmp_path):
    from asg_stagecraft.runtime.config import Settings

    RecordingGemini.built = []
    monkeypatch.setattr(provider_module, "GeminiProvider", RecordingGemini)
    same = Settings(api_key="k", model="gemini-3.5-flash-lite", output_root=tmp_path)
    assert isinstance(provider_module.provider_from_settings(same), RecordingGemini)
    assert len(RecordingGemini.built) == 1

    RecordingGemini.built = []
    split = Settings(
        api_key="k",
        model="gemini-3.5-flash-lite",
        output_root=tmp_path,
        rpm_limit=15,
        stage_model="gemini-3.1-flash-lite",
        stage_rpm_limit=10,
    )
    routed = provider_module.provider_from_settings(split)
    assert isinstance(routed, provider_module.RoutedProvider)
    main, stage = RecordingGemini.built
    assert (main["model"], main["rpm_limit"]) == ("gemini-3.5-flash-lite", 15)
    assert (stage["model"], stage["rpm_limit"], stage["api_key"]) == (
        "gemini-3.1-flash-lite",
        10,
        "k",
    )
    assert routed.stage_model_name == "gemini-3.1-flash-lite"


def test_each_model_and_key_has_its_own_rpm_window() -> None:
    """Gemini counts quota per project and model; the limiter used to key on the RPM alone."""
    first = GeminiProvider("key-one", "model-a", rpm_limit=41, rpm_reserve=1)
    again = GeminiProvider("key-one", "model-a", rpm_limit=41, rpm_reserve=1)
    other_model = GeminiProvider("key-one", "model-b", rpm_limit=41, rpm_reserve=1)
    other_key = GeminiProvider("key-two", "model-a", rpm_limit=41, rpm_reserve=1)
    assert first._limiter is again._limiter
    assert first._limiter is not other_model._limiter
    assert first._limiter is not other_key._limiter
    # The registry names a key by its fingerprint, never by the key itself.
    assert not any("key-one" in key or "key-two" in key for key in provider_module._LIMITERS)
