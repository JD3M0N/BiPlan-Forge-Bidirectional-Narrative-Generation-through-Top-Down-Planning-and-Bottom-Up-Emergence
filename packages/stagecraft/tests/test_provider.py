import json
from datetime import UTC, datetime
from types import SimpleNamespace

import asg_stagecraft.runtime.provider as provider_module
import pytest
from asg_stagecraft.runtime.budget import QuotaLedger, QuotaSlot, window_bounds
from asg_stagecraft.runtime.errors import (
    EmptyResponseError,
    GeminiBillingQuotaError,
    GeminiDailyQuotaError,
    ProviderDailyQuotaError,
    ProviderError,
    StructuredResponseError,
)
from asg_stagecraft.runtime.provider import GeminiProvider, _gemini_response_schema
from asg_stagecraft.schemas import LLMUsageRecord, StoryRequest

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
    """A real GeminiProvider, one retry and no RPM pacing, talking to FakeModels."""
    provider = GeminiProvider("fake-key", "fake-flash", max_retries=1)
    provider._limiter = None
    provider._client = SimpleNamespace(models=FakeModels(response, error))
    return provider


@pytest.fixture(autouse=True)
def no_real_waits(monkeypatch):
    """Retries never sleep for real: a test that cares about a wait overrides this on top."""
    monkeypatch.setattr(provider_module, "countdown_wait", lambda *args: None)
    monkeypatch.setattr(provider_module, "retry_delay", lambda attempt, details: 0)


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


class FlakyModels(FakeModels):
    """Fails once with a transport error, then answers normally."""

    def generate_content(self, **kwargs):
        self.generate_calls.append(kwargs)
        if len(self.generate_calls) == 1:
            raise type("ConnectError", (Exception,), {})("getaddrinfo failed")
        return SimpleNamespace(text="respuesta", usage_metadata=None)


def test_a_transient_transport_error_is_retried_then_succeeds() -> None:
    provider = provider_with()
    provider.max_retries = 3
    provider._client.models = FlakyModels()
    assert (
        provider.generate_text(system_instruction="test", prompt="test", profile="prose")
        == "respuesta"
    )
    assert len(provider._client.models.generate_calls) == 2
    assert [record.status for record in provider.usage_records] == ["failed", "succeeded"]


def test_a_transport_error_that_never_recovers_is_wrapped_and_reported() -> None:
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


def test_authentication_errors_fail_immediately_without_retrying() -> None:
    provider = provider_with(error=Exception("401 invalid API key"))
    provider.max_retries = 3
    with pytest.raises(ProviderError):
        provider.generate_text(system_instruction="test", prompt="test", profile="prose")
    assert len(provider._client.models.generate_calls) == 1


@pytest.mark.parametrize(
    ("error_text", "expected_quota_id"),
    [
        (
            "429 Quota exceeded for metric: requests_per_day, 'quotaId': 'PerDay'",
            "PerDay",
        ),
        (
            FREE_TIER_DAILY_429,
            "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
        ),
    ],
    ids=["explicit-quota-id", "billing-worded-daily-quota-is-not-mistaken-for-billing"],
)
def test_a_daily_quota_is_never_retried_and_keeps_its_id(
    error_text, expected_quota_id, tmp_path
) -> None:
    """MED-1: reading the text before the quota ID turned three daily quotas into billing.

    Outside a chain the provider charges its own ledger slot, and a spent daily quota keeps the
    slot out until its window resets, not for the ~55 s retry_delay Gemini sends with it.
    """
    ledger = QuotaLedger(tmp_path / "budget.sqlite3")
    slot = QuotaSlot("gemini", "fake-flash", "pacific_day", max_requests=500)
    provider = provider_with(error=Exception(error_text))
    provider.max_retries = 3
    provider.quota = (ledger, slot)
    with pytest.raises(GeminiDailyQuotaError) as raised:
        provider._generate("text", provider._client.models.generate_content)
    assert raised.value.details["quota_id"] == expected_quota_id
    assert len(provider._client.models.generate_calls) == 1
    assert ledger.usage(slot) == (1, 0)
    assert ledger.exhausted_until(slot) == ledger.resets_at(slot)


def test_a_billing_limit_named_only_in_the_text_is_still_billing() -> None:
    provider = provider_with(error=Exception("429 Your spend cap was reached, check billing."))
    with pytest.raises(GeminiBillingQuotaError):
        provider._generate("text", provider._client.models.generate_content)


def test_the_attempts_of_one_call_share_its_id_and_keep_their_own_latency(monkeypatch) -> None:
    """MED-2: every attempt had its own call_id and a duration that added up the earlier ones."""
    clock = iter([0.0, 3.0, 100.0, 104.0])
    provider = provider_with()
    provider.max_retries = 3
    provider._client.models = FlakyModels()
    monkeypatch.setattr(provider_module, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(provider_module, "retry_delay", lambda attempt, details: 5)
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


def test_every_named_profile_reaches_the_request_as_its_documented_temperature() -> None:
    """The five named profiles are the only source of temperature, with no per-instance state."""
    expected = {"extraction": 0.15, "review": 0.2, "planning": 0.5, "prose": 0.9, "rewrite": 0.35}
    assert provider_module._DEFAULT_GENERATION_PROFILES == expected
    for profile, temperature in expected.items():
        provider = provider_with(SimpleNamespace(text="respuesta", usage_metadata=None))
        provider.generate_text(system_instruction="test", prompt="test", profile=profile)
        config = provider._client.models.generate_calls[-1]["config"]
        assert config.temperature == temperature
        assert provider._temperature(profile) == temperature
    structured_provider = provider_with(
        SimpleNamespace(parsed=None, text=valid_story_request_json())
    )
    structured_provider.generate_structured(
        system_instruction="test", prompt="test", schema=StoryRequest, profile="extraction"
    )
    assert structured_provider._client.models.generate_calls[-1]["config"].temperature == 0.15


def test_unknown_temperature_profile_is_rejected() -> None:
    """An unknown profile name fails fast instead of silently borrowing another temperature."""
    provider = provider_with(SimpleNamespace(text="respuesta", usage_metadata=None))
    with pytest.raises(ValueError, match="not-a-real-profile"):
        provider.generate_text(
            system_instruction="test", prompt="test", profile="not-a-real-profile"
        )


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
        budget_path=tmp_path / "budget.sqlite3",
    )
    routed = provider_module.provider_from_settings(split)
    assert isinstance(routed, provider_module.RoutedProvider)
    # MED-1: without a chain each model still charges its own daily slot.
    assert [provider.quota[1].key for provider in (routed.main, routed.stage)] == [
        "gemini:gemini-3.5-flash-lite",
        "gemini:gemini-3.1-flash-lite",
    ]
    main, stage = RecordingGemini.built
    assert (main["model"], main["rpm_limit"]) == ("gemini-3.5-flash-lite", 15)
    assert (stage["model"], stage["rpm_limit"], stage["api_key"]) == (
        "gemini-3.1-flash-lite",
        10,
        "k",
    )
    assert routed.stage_model_name == "gemini-3.1-flash-lite"


def test_each_model_and_key_has_its_own_rpm_window(monkeypatch) -> None:
    """Gemini counts quota per project and model; the limiter used to key on the RPM alone."""
    monkeypatch.setattr("google.genai.Client", lambda **kwargs: SimpleNamespace())
    first = GeminiProvider("key-one", "model-a", rpm_limit=41, rpm_reserve=1)
    again = GeminiProvider("key-one", "model-a", rpm_limit=41, rpm_reserve=1)
    other_model = GeminiProvider("key-one", "model-b", rpm_limit=41, rpm_reserve=1)
    other_key = GeminiProvider("key-two", "model-a", rpm_limit=41, rpm_reserve=1)
    assert first._limiter is again._limiter
    assert first._limiter is not other_model._limiter
    assert first._limiter is not other_key._limiter
    # The registry names a key by its fingerprint, never by the key itself.
    assert not any("key-one" in key or "key-two" in key for key in provider_module._LIMITERS)


@pytest.mark.parametrize(
    ("window", "moment", "label", "reset"),
    [
        ("pacific_day", "2026-10-08T06:59", "2026-10-07", "2026-10-08T07:00"),
        ("pacific_day", "2026-12-01T08:00", "2026-12-01", "2026-12-02T08:00"),
        # 1 November 2026 ends daylight time: the next midnight is an hour later in UTC.
        ("pacific_day", "2026-11-01T08:00", "2026-11-01", "2026-11-02T08:00"),
        ("utc_day", "2026-10-08T23:59", "2026-10-08", "2026-10-09T00:00"),
        ("utc_month", "2026-12-15T12:00", "2026-12", "2027-01-01T00:00"),
    ],
    ids=["gemini-pdt", "gemini-pst", "gemini-dst-ends", "groq-day", "mistral-month"],
)
def test_each_quota_window_resets_when_its_provider_does(window, moment, label, reset) -> None:
    def utc(text):
        return datetime.fromisoformat(text).replace(tzinfo=UTC)

    assert window_bounds(window, utc(moment)) == (label, utc(reset))


class QuotaFake:
    """Answer with its own name, or report its daily quota spent, recording like a provider."""

    def __init__(self, model_name: str, *, spent: bool = False) -> None:
        self.model_name = model_name
        self.spent = spent
        self.calls = 0
        self.usage_records = []

    def generate_text(self, **kwargs):
        self.calls += 1
        if self.spent:
            raise ProviderDailyQuotaError("cupo agotado", details={"retry_delay": None})
        self.usage_records.append(
            LLMUsageRecord(
                call_id="c",
                operation="text",
                stage="planning",
                attempt=1,
                status="succeeded",
                model=self.model_name,
                timestamp=datetime.now(UTC),
                total_tokens=10,
            )
        )
        return self.model_name


@pytest.mark.parametrize(
    ("first_spent", "first_cap", "second_spent", "expected"),
    [
        (True, 0, False, "second"),
        (False, 1, False, "second"),
        (True, 0, True, None),
    ],
    ids=["declared-by-a-429", "known-from-the-ledger", "whole-chain-spent"],
)
def test_the_chain_moves_on_when_a_slot_is_spent(
    tmp_path, first_spent, first_cap, second_spent, expected
) -> None:
    ledger = QuotaLedger(tmp_path / "budget.sqlite3")
    slots = [QuotaSlot("gemini", "first", max_tokens=first_cap), QuotaSlot("groq", "second")]
    fakes = [QuotaFake("first", spent=first_spent), QuotaFake("second", spent=second_spent)]
    chain = provider_module.FailoverProvider(list(zip(slots, fakes, strict=True)), ledger)
    notices = []
    chain.wait_callback = lambda seconds, reason: notices.append(reason)
    ask = {"system_instruction": "s", "prompt": "p", "profile": "prose"}
    if expected is None:
        with pytest.raises(ProviderDailyQuotaError, match="cadena"):
            chain.generate_text(**ask)
        return
    assert chain.generate_text(**ask) == expected
    assert [record.model for record in chain.usage_records] == ["second"]
    assert ledger.usage(slots[1]) == (1, 10)
    # A cap the ledger already knows costs no request; a 429 is remembered until the reset.
    assert fakes[0].calls == (1 if first_spent else 0)
    if first_spent:
        assert ledger.exhausted_until(slots[0]) == ledger.resets_at(slots[0])
        assert notices == ["gemini:first agotado; sigo con groq:second"]
        assert chain.generate_text(**ask) == "second" and fakes[0].calls == 1


class FakeHTTP:
    """Stand in for httpx.Client, replying with (status, payload) pairs in order."""

    def __init__(self, replies) -> None:
        self.replies = list(replies)
        self.bodies = []

    def post(self, path, json):
        self.bodies.append(json)
        status, payload = self.replies.pop(0)
        text = payload if isinstance(payload, str) else ""
        return SimpleNamespace(status_code=status, headers={}, text=text, json=lambda: payload)


def completion(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "total_tokens": 30,
            "completion_tokens_details": {"reasoning_tokens": 5},
        },
    }


@pytest.mark.parametrize(
    ("replies", "formats"),
    [
        ([(200, completion(valid_story_request_json()))], ["json_schema"]),
        (
            [
                (400, "response_format json_schema is not supported with this model"),
                (200, completion(valid_story_request_json())),
            ],
            ["json_schema", "json_object"],
        ),
        ([(429, "Rate limit reached on tokens per day (TPD): Limit 200000")], ["json_schema"]),
    ],
    ids=["json-schema", "falls-back-to-json-object", "daily-cap-is-not-retried"],
)
def test_an_openai_compatible_provider_returns_validated_json(replies, formats) -> None:
    provider = provider_module.OpenAICompatibleProvider(
        "fake-key", "openai/gpt-oss-120b", "https://groq.invalid", label="Groq", max_retries=2
    )
    provider._limiter = None
    provider._client = FakeHTTP(replies)
    ask = {"system_instruction": "s", "prompt": "p", "schema": StoryRequest, "profile": "planning"}
    if replies[-1][0] == 429:
        with pytest.raises(ProviderDailyQuotaError):
            provider.generate_structured(**ask)
    else:
        assert provider.generate_structured(**ask).title == "Título"
        record = provider.usage_records[-1]
        assert (record.total_tokens, record.thoughts_tokens) == (30, 5)
    bodies = provider._client.bodies
    assert [body["response_format"]["type"] for body in bodies] == formats
    assert "additionalProperties" not in json.dumps(bodies[0]["response_format"])
    if "json_object" in formats:
        assert "JSON schema" in bodies[-1]["messages"][0]["content"]


class RecordingCompatible:
    """Stand in for OpenAICompatibleProvider, keeping what the factory built it with."""

    def __init__(self, api_key, model_name, base_url, **kwargs):
        self.model_name = model_name


CHAIN_ENV = {
    "GEMINI_API_KEY": "g",
    "GEMINI_MODEL": "gemini-3.5-flash-lite",
    "GROQ_API_KEY": "q",
    "GROQ_MODELS": "openai/gpt-oss-120b,openai/gpt-oss-20b",
    "MISTRAL_API_KEY": "m",
}
GROQ_AND_MISTRAL = [
    "groq:openai/gpt-oss-120b",
    "groq:openai/gpt-oss-20b",
    "mistral:mistral-small-latest",
]


@pytest.mark.parametrize(
    ("chain", "stage_model", "slots"),
    [
        ("groq,mistral", "", GROQ_AND_MISTRAL),
        # Every call, the performance included, spends 3.5 first, then 3.1, then the rest.
        (
            "gemini, groq, mistral",
            "gemini-3.1-flash-lite",
            ["gemini:gemini-3.5-flash-lite", "gemini:gemini-3.1-flash-lite", *GROQ_AND_MISTRAL],
        ),
    ],
    ids=["no-gemini-needs-no-gemini-key", "second-gemini-model-comes-before-groq"],
)
def test_the_factory_builds_the_chain_from_the_environment(
    monkeypatch, tmp_path, chain, stage_model, slots
):
    from asg_stagecraft.runtime.config import load_settings

    (tmp_path / "packages").mkdir()
    (tmp_path / "Stories").mkdir()
    monkeypatch.setattr(provider_module, "GeminiProvider", RecordingGemini)
    monkeypatch.setattr(provider_module, "OpenAICompatibleProvider", RecordingCompatible)
    for name in ("GEMINI_STAGE_API_KEY", "GEMINI_STAGE_RPM_LIMIT", "MISTRAL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in {**CHAIN_ENV, "ASG_LLM_CHAIN": chain}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("GEMINI_STAGE_MODEL", stage_model)
    if "gemini" not in chain:
        monkeypatch.delenv("GEMINI_API_KEY")
    provider = provider_module.provider_from_settings(load_settings(tmp_path))
    assert isinstance(provider, provider_module.FailoverProvider)
    assert [slot.key for slot, _ in provider.entries] == slots
    assert provider.ledger.path == tmp_path / ".cache" / "llm_budget.sqlite3"


def test_the_quota_panel_adds_up_each_provider_from_logs_and_ledger(tmp_path) -> None:
    from asg_stagecraft.runtime.config import ChainEntry, Settings
    from asg_stagecraft.tools.budget import report

    runs = tmp_path / "Stories" / "Stagecraft"
    calls = [
        ("g-main", "succeeded", None, "2026-10-08T15:00:00+00:00"),
        ("g-stage", "succeeded", None, "2026-10-08T15:01:00+00:00"),
        ("g-main", "failed", "500", "2026-10-08T15:02:00+00:00"),
        # A 429 consumed nothing, and yesterday's call belongs to a window already reset.
        ("g-main", "failed", "429", "2026-10-08T15:03:00+00:00"),
        ("g-main", "succeeded", None, "2026-10-07T12:00:00+00:00"),
    ]
    lines = [
        {"model": m, "status": s, "error_code": e, "timestamp": t, "total_tokens": 100}
        for m, s, e, t in calls
    ]
    run = runs / "20261008-run"
    run.mkdir(parents=True)
    (run / "llm_calls.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines), encoding="utf-8"
    )
    (run / "metadata.json").write_text('{"status": "completed"}', encoding="utf-8")
    (run / "llm_usage.json").write_text('{"calls": 3, "total_tokens": 300}', encoding="utf-8")
    groq = QuotaSlot("groq", "q", max_requests=1000, max_tokens=200_000)
    settings = Settings(
        api_key="k",
        model="g-main",
        stage_model="g-stage",
        output_root=runs,
        budget_path=tmp_path / "budget.sqlite3",
        chain=(
            ChainEntry(QuotaSlot("gemini", "", "pacific_day", max_requests=500)),
            ChainEntry(groq, "k", "https://example.invalid", 30, "Groq"),
        ),
    )
    QuotaLedger(settings.budget_path).mark_exhausted(groq)
    panel = report(settings, now=datetime(2026, 10, 8, 18, tzinfo=UTC))
    gemini = next(line for line in panel if line.startswith("Gemini"))
    assert "3/1.000 peticiones hoy · quedan 997" in gemini
    assert any(line.strip().startswith("q ") and "AGOTADO" in line for line in panel)
    assert panel[-1] == "Caben aprox.: Gemini 332 · Groq 0."


@pytest.mark.parametrize(
    ("story_format", "cap", "refused"),
    [("narrative", 500, False), ("narrative", 20, True), ("simulated", 20, False)],
    ids=["fits", "does-not-fit", "no-run-of-that-format-to-estimate-from"],
)
def test_generate_story_refuses_a_run_that_does_not_fit_in_todays_quota(
    tmp_path, story_format, cap, refused
) -> None:
    """MED-1: 060405 was launched 5 s after 054422 spent the day and died on its first call."""
    from asg_stagecraft.runtime.config import Settings
    from asg_stagecraft.tools.budget import preflight

    run = tmp_path / "Stories" / "Stagecraft" / "20261001-000000-una"
    run.mkdir(parents=True)
    (run / "metadata.json").write_text('{"status": "completed"}', encoding="utf-8")
    (run / "llm_usage.json").write_text('{"calls": 16, "total_tokens": 84000}', encoding="utf-8")
    settings = Settings(
        api_key="k",
        model="g-main",
        output_root=run.parent,
        budget_path=tmp_path / "budget.sqlite3",
        gemini_daily_requests=cap,
    )
    slot = settings.quota_entries()[0].slot
    QuotaLedger(settings.budget_path).record(slot, requests=10, tokens=1000)
    refusal = preflight(settings, story_format)
    if refused:
        assert "~16 llamadas y quedan 10" in refusal and "--force" in refusal
    else:
        assert refusal is None
