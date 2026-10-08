"""Language-model provider abstraction, its Gemini and OpenAI-compatible clients, and routing."""

import hashlib
import json
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from ..schemas import LLMUsageRecord
from .budget import QuotaLedger, QuotaSlot
from .config import ChainEntry, Settings
from .errors import (
    EmptyResponseError,
    GeminiBillingQuotaError,
    GeminiDailyQuotaError,
    GeminiRPMError,
    GeminiTPMError,
    ProviderDailyQuotaError,
    ProviderError,
    StructuredResponseError,
)
from .quota import (
    SlidingWindowLimiter,
    TokenWindowLimiter,
    countdown_wait,
    retry_delay,
    retry_details,
)

T = TypeVar("T", bound=BaseModel)
# One RPM limiter per (key fingerprint, model, capacity), shared by every provider in the process.
# Gemini counts its quota per project and per model, so two models - or two keys - never share a
# window; before 7.4 the key was the capacity alone, and a performance model paced at the same RPM
# as the main one would have waited on the main one's calls.
_LIMITERS: dict[tuple[str, str, int], SlidingWindowLimiter] = {}
_LIMITERS_LOCK = threading.Lock()

# The pipeline stages whose calls go to the performance model when one is configured. Only the
# performance: it spends most of a simulated run's calls, casting is one strictly validated call,
# and narration writes the text that is evaluated, which stays on the main model so it can be
# compared with the runs before 7.4.
STAGE_MODEL_STAGES = frozenset({"performance"})
# Both settings below are module constants, not constructor arguments: no call site in
# the repository ever configured them, and the per-instance copies only survived because
# the code read them through getattr defaults to tolerate a test double that skips
# __init__. Reading the constant directly keeps one source of truth for the temperatures
# CLAUDE.md documents, and a future caller that needs to vary them can reintroduce the
# parameter along with the reason it exists.
_STRUCTURED_VALIDATION_RETRIES = 1

_DEFAULT_GENERATION_PROFILES: dict[str, float] = {
    "extraction": 0.15,
    "review": 0.2,
    "planning": 0.5,
    "prose": 0.9,
    "rewrite": 0.35,
}

# The token-count preflight a TPM limit needs. It is recorded, but it is not a call.
COUNT_TOKENS_OPERATION = "count_tokens"

# Where in the pipeline a model call is made: the pipeline sets it around every agent call and
# the provider reads it when recording, so the cost of a run can be split by stage and agent
# without the provider knowing either. Unset, records fall back to the operation, as before 7.2.
_CALL_CONTEXT: ContextVar[tuple[str, str]] = ContextVar("llm_call_context", default=("", ""))
_DECISION_CONTEXT: ContextVar[str] = ContextVar("stage_decision_context", default="")


@contextmanager
def decision_context(decision_id: str) -> Iterator[None]:
    """Link one stage decision with all provider attempts it causes."""
    token = _DECISION_CONTEXT.set(decision_id)
    try:
        yield
    finally:
        _DECISION_CONTEXT.reset(token)


@contextmanager
def call_context(stage: str, agent: str) -> Iterator[None]:
    """Tag every model call made inside the block with its pipeline stage and agent."""
    token = _CALL_CONTEXT.set((stage, agent))
    try:
        yield
    finally:
        _CALL_CONTEXT.reset(token)


def current_call_context() -> tuple[str, str]:
    """Return the (stage, agent) the pipeline declared for the call being made now."""
    return _CALL_CONTEXT.get()


def _key_fingerprint(api_key: str) -> str:
    """Name a key's quota bucket without keeping the key itself in the limiter registry."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def _shared_limiter(
    api_key: str, model_name: str, rpm_limit: int, rpm_reserve: int
) -> SlidingWindowLimiter:
    """Return the process-wide RPM limiter for one key, model and capacity."""
    capacity = max(1, rpm_limit - rpm_reserve)
    with _LIMITERS_LOCK:
        return _LIMITERS.setdefault(
            (_key_fingerprint(api_key), model_name, capacity), SlidingWindowLimiter(capacity)
        )


def _gemini_response_schema(schema: type[BaseModel]) -> dict:
    """Return a Gemini-compatible copy of a Pydantic JSON schema.

    Gemini validates the requested structure, while Pydantic remains the
    authority for stricter local rules such as ``extra="forbid"``. Some
    Gemini models reject the JSON Schema ``additionalProperties`` keyword,
    so it must not cross the provider boundary.
    """

    def sanitize(value):
        """Recursively drop the ``additionalProperties`` keyword."""
        if isinstance(value, dict):
            return {
                key: sanitize(item) for key, item in value.items() if key != "additionalProperties"
            }
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        return value

    return sanitize(schema.model_json_schema())


def _safe_provider_error(exc: Exception) -> ProviderError:
    """Classify provider failures without exposing request or credential data."""
    message = str(exc).casefold()
    diagnostic = retry_details(exc)
    status = diagnostic.get("status")
    if status in {401, 403} or any(
        token in message
        for token in (
            "api key",
            "unauth",
            "permission_denied",
            "permission denied",
            "401",
            "403",
        )
    ):
        summary = "Gemini rechazó la autenticación o los permisos configurados."
        recommendation = "Comprueba GEMINI_API_KEY y el acceso al modelo seleccionado."
    elif status == 400:
        summary = "Gemini rechazó los parámetros o el esquema de la solicitud."
        recommendation = "Revisa el esquema indicado y la compatibilidad del modelo configurado."
    elif status == 404:
        summary = "Gemini no encontró el modelo o recurso configurado."
        recommendation = "Comprueba GEMINI_MODEL y, si la usas, GEMINI_STAGE_MODEL."
    elif any(token in message for token in ("quota", "rate limit", "resource_exhausted", "429")):
        summary = "Gemini rechazó la solicitud por cuota o límite de uso."
        recommendation = "Espera unos minutos o revisa la cuota del proyecto de Gemini."
    elif _is_transient_transport_error(exc):
        summary = "No fue posible comunicarse con Gemini."
        recommendation = "Comprueba la conexión y vuelve a intentarlo."
    else:
        summary = "Gemini no pudo completar la solicitud."
        recommendation = "Vuelve a intentarlo y consulta el registro local si persiste."
    return ProviderError(
        summary,
        details={
            "exception_type": type(exc).__name__,
            **{key: value for key, value in diagnostic.items() if value is not None},
        },
        recommendations=[recommendation],
    )


def _quota_error_type(exc: Exception, details: dict) -> type[ProviderError]:
    """Name the quota a 429 exhausted, trusting what Gemini declares over what its text says.

    The standard free-tier 429 asks to "check your plan and billing details", so reading the
    text first filed every exhausted daily quota as a billing limit: the three such failures in
    the corpus all carry quota_id GenerateRequestsPerDayPerProjectPerModel-FreeTier. The text is
    now the last resort, used only when neither the quota ID nor the metric says anything.
    """
    quota_id = str(details.get("quota_id") or "").casefold()
    metric = str(details.get("metric") or "").casefold()
    declared = f"{quota_id} {metric}"
    if "day" in quota_id or "daily" in declared:
        return GeminiDailyQuotaError
    if "billing" in declared or "spend" in declared:
        return GeminiBillingQuotaError
    text = str(exc).casefold()
    if not quota_id and not metric and ("billing" in text or "spend" in text):
        return GeminiBillingQuotaError
    return GeminiTPMError if "token" in metric else GeminiRPMError


def _is_transient_transport_error(exc: Exception) -> bool:
    """Recognize retryable transport failures across supported HTTP clients."""
    current: BaseException | None = exc
    seen: set[int] = set()
    class_markers = {
        "connecterror",
        "connecttimeout",
        "readtimeout",
        "writetimeout",
        "pooltimeout",
        "networkerror",
        "transporterror",
        "timeouterror",
        "connectionerror",
    }
    message_markers = (
        "connection reset",
        "connection refused",
        "connection aborted",
        "temporary failure",
        "temporarily unavailable",
        "timed out",
        "timeout",
        "getaddrinfo",
        "name resolution",
        "dns",
        "network is unreachable",
        "server disconnected",
        "remote protocol error",
    )
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        name = type(current).__name__.casefold()
        message = str(current).casefold()
        if name in class_markers or isinstance(current, (OSError, ConnectionError, TimeoutError)):
            return True
        if any(marker in message for marker in message_markers):
            return True
        current = current.__cause__ or current.__context__
    return False


class LanguageModelProvider(Protocol):
    """Define the language-model operations required by story agents."""

    model_name: str

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[T], profile: str
    ) -> T:
        """Generate and validate a structured response."""
        ...

    def generate_text(self, *, system_instruction: str, prompt: str, profile: str) -> str:
        """Generate an unstructured text response."""
        ...


class _RecordingProvider:
    """Retry, pace, validate and record model calls; subclasses only speak to their client.

    Everything here reads its tuning through getattr defaults, because the tests build
    providers with __new__ and set only the client and the model name.
    """

    model_name: str
    provider_label = "Gemini"
    quota_recommendation = "Espera a que se restablezca la cuota o revisa tu plan en AI Studio."

    def _temperature(self, profile: str) -> float:
        """Look up the configured temperature for an explicit generation profile."""
        try:
            return float(_DEFAULT_GENERATION_PROFILES[profile])
        except KeyError as exc:
            raise ValueError(f"Unknown generation profile: {profile!r}") from exc

    def _preflight_tokens(self, prompt: str, system_instruction: str) -> None:
        """Reserve tokens before a call; only a provider that can count them does anything."""

    def _usage(self, response) -> dict[str, int]:
        """Return the token counters of a response, by LLMUsageRecord field name."""
        return {}

    def _retry_details(self, exc: Exception) -> dict[str, object]:
        """Read the status, delay and quota diagnostics a failed request carries."""
        return retry_details(exc)

    def _is_spent_quota(self, exc: Exception, details: dict) -> bool:
        """Say whether a 429 names an allowance that no retry within minutes can recover."""
        quota_id = str(details.get("quota_id") or "").casefold()
        metric = str(details.get("metric") or "").casefold()
        return any(
            marker in quota_id or marker in metric
            for marker in ("day", "daily", "billing", "spend")
        )

    def _quota_error_type(self, exc: Exception, details: dict) -> type[ProviderError]:
        """Name the quota a final 429 exhausted."""
        return _quota_error_type(exc, details)

    def _safe_error(self, exc: Exception) -> ProviderError:
        """Classify an unexpected client failure without leaking the request."""
        return _safe_provider_error(exc)

    def _emit_record(self, record: LLMUsageRecord) -> None:
        """Emit record."""
        if not hasattr(self, "usage_records"):
            self.usage_records = []
        self.usage_records.append(record)
        callback = getattr(self, "usage_callback", None)
        if callback:
            callback(record)

    def _record_auxiliary(
        self, operation: str, started: float, status: str, error_code: str | None = None
    ) -> None:
        """Record one auxiliary request, such as a token count, which is never a call."""
        stage, agent = current_call_context()
        self._emit_record(
            LLMUsageRecord(
                call_id=uuid.uuid4().hex,
                decision_id=_DECISION_CONTEXT.get(),
                operation=operation,
                stage=stage or operation,
                agent=agent,
                attempt=1,
                status=status,
                error_code=error_code,
                model=self.model_name,
                timestamp=datetime.now(UTC),
                duration_seconds=time.monotonic() - started,
            )
        )

    def _record(
        self,
        response,
        operation: str,
        call_id: str,
        attempt: int,
        duration: float,
        waited: float,
    ) -> None:
        """Record the attempt that succeeded, with its own latency and the wait before it."""
        stage, agent = current_call_context()
        record = LLMUsageRecord(
            call_id=call_id,
            decision_id=_DECISION_CONTEXT.get(),
            operation=operation,
            stage=stage or operation,
            agent=agent,
            attempt=attempt + 1,
            status="succeeded",
            model=self.model_name,
            timestamp=datetime.now(UTC),
            duration_seconds=duration,
            retries=attempt,
            wait_seconds=waited,
            **self._usage(response),
        )
        self._emit_record(record)

    def _record_failure(
        self,
        operation: str,
        call_id: str,
        attempt: int,
        duration: float,
        waited: float,
        error_code: str,
    ) -> None:
        """Record one failed attempt, with its own latency and the wait before it."""
        stage, agent = current_call_context()
        self._emit_record(
            LLMUsageRecord(
                call_id=call_id,
                decision_id=_DECISION_CONTEXT.get(),
                operation=operation,
                stage=stage or operation,
                agent=agent,
                attempt=attempt + 1,
                status="failed",
                error_code=error_code,
                model=self.model_name,
                timestamp=datetime.now(UTC),
                duration_seconds=duration,
                wait_seconds=waited,
                retries=attempt,
            )
        )

    def _generate(self, operation: str, invoke):
        """Call the model, retrying what is transient, and record every attempt.

        All attempts share one call_id, so a retried call regroups as one. Each record carries
        its own attempt's latency and the waiting just before it, never the sum of earlier
        attempts: 7.1 logged one actor turn as 120, 244, 370 and 382 seconds.
        """
        call_id = uuid.uuid4().hex
        pending_wait = 0.0
        max_retries = getattr(self, "max_retries", 1)
        limiter = getattr(self, "_limiter", None)
        callback = getattr(self, "wait_callback", None)
        if not hasattr(self, "usage_records"):
            self.usage_records = []
        # GEMINI_MAX_RETRIES describes retries after the initial request.
        for attempt in range(max_retries + 1):
            waited, pending_wait = pending_wait, 0.0
            if limiter:
                waited += limiter.acquire(callback)
            started = time.monotonic()
            try:
                response = invoke()
                self._record(
                    response, operation, call_id, attempt, time.monotonic() - started, waited
                )
                return response
            except Exception as exc:
                elapsed = time.monotonic() - started
                details = self._retry_details(exc)
                status = details.get("status")
                self._record_failure(
                    operation,
                    call_id,
                    attempt,
                    elapsed,
                    waited,
                    str(status or type(exc).__name__),
                )
                permanent_quota = status == 429 and self._is_spent_quota(exc, details)
                transient = (
                    status in {408, 429}
                    or (isinstance(status, int) and 500 <= status < 600)
                    or _is_transient_transport_error(exc)
                )
                if permanent_quota or not transient or attempt >= max_retries:
                    if status == 429:
                        error_type = self._quota_error_type(exc, details)
                        raise error_type(
                            f"{self.provider_label} agotó la cuota para {self.model_name}.",
                            details={
                                **details,
                                "model": self.model_name,
                                "attempts": attempt + 1,
                                "retries": attempt,
                            },
                            recommendations=[self.quota_recommendation],
                        ) from exc
                    raise
                delay = retry_delay(attempt + 1, details)
                if delay > getattr(self, "max_retry_delay", 120):
                    raise GeminiRPMError(
                        f"{self.provider_label} indicó una espera superior al máximo configurado.",
                        details={**details, "model": self.model_name},
                        recommendations=["Reanuda el trabajo cuando se restablezca la cuota."],
                    ) from exc
                countdown_wait(delay, f"reintento solicitado por {self.provider_label}", callback)
                pending_wait = delay

    def _invoke_structured(
        self, prompt: str, system_instruction: str, schema: type[BaseModel], temperature: float
    ):
        """Send one structured request through the client and return its raw response."""
        raise NotImplementedError

    def _invoke_text(self, prompt: str, system_instruction: str, temperature: float):
        """Send one free-text request through the client and return its raw response."""
        raise NotImplementedError

    def _structured_payload(self, response):
        """Return a parsed object, or the JSON text to validate, from a structured response."""
        raise NotImplementedError

    def _text_payload(self, response) -> str:
        """Return the text of a free-text response."""
        raise NotImplementedError

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[T], profile: str
    ) -> T:
        """Generate structured."""
        temperature = self._temperature(profile)
        validation_retries = _STRUCTURED_VALIDATION_RETRIES
        current_prompt = prompt
        last_errors: list[dict[str, str]] = []
        for validation_attempt in range(validation_retries + 1):
            try:
                self._preflight_tokens(current_prompt, system_instruction)

                def invoke(prompt_snapshot: str = current_prompt):
                    """Request structured output with this attempt's bound prompt."""
                    return self._invoke_structured(
                        prompt_snapshot, system_instruction, schema, temperature
                    )

                response = self._generate(
                    f"structured:{schema.__name__}",
                    invoke,
                )
                payload = self._structured_payload(response)
                if payload is None or (isinstance(payload, str) and not payload):
                    raise EmptyResponseError(f"{self.provider_label} devolvió una respuesta vacía.")
                if isinstance(payload, str):
                    return schema.model_validate_json(payload)
                return schema.model_validate(payload)
            except ProviderError:
                raise
            except ValidationError as exc:
                last_errors = [
                    {
                        "location": ".".join(str(part) for part in error.get("loc", ())) or "$",
                        "type": str(error.get("type", "validation_error")),
                        "message": str(error.get("msg", "validation failed"))[:240],
                    }
                    for error in exc.errors(
                        include_url=False, include_context=False, include_input=False
                    )
                ]
                if validation_attempt >= validation_retries:
                    raise StructuredResponseError(
                        f"{self.provider_label} devolvió datos incompatibles con "
                        f"{schema.__name__}.",
                        details={
                            "schema": schema.__name__,
                            "attempts": validation_attempt + 1,
                            "validation_errors": last_errors,
                        },
                        recommendations=[
                            "Revisa los errores de validación guardados o usa un modelo más capaz."
                        ],
                    ) from exc
                correction = json.dumps(last_errors, ensure_ascii=False)
                current_prompt = (
                    f"{prompt}\n\nSTRUCTURED OUTPUT CORRECTION:\n"
                    f"The previous response failed validation at: {correction}. "
                    "Return a complete replacement that exactly matches the requested schema."
                )
            except Exception as exc:
                raise self._safe_error(exc) from exc
        raise AssertionError("structured validation loop ended unexpectedly")

    def generate_text(self, *, system_instruction: str, prompt: str, profile: str) -> str:
        """Generate text."""
        temperature = self._temperature(profile)
        try:
            self._preflight_tokens(prompt, system_instruction)

            def invoke():
                """Request free-form text with the bound prompt."""
                return self._invoke_text(prompt, system_instruction, temperature)

            response = self._generate("text", invoke)
            text = self._text_payload(response)
            if not text or not text.strip():
                raise EmptyResponseError(f"{self.provider_label} devolvió una respuesta vacía.")
            return text.strip()
        except ProviderError:
            raise
        except Exception as exc:
            raise self._safe_error(exc) from exc


class GeminiProvider(_RecordingProvider):
    """Encapsulate all coupling to the Google GenAI client."""

    def __init__(
        self,
        api_key: str,
        model_name: str,
        *,
        rpm_limit: int = 15,
        rpm_reserve: int = 1,
        tpm_limit: int = 0,
        max_retries: int = 3,
        max_retry_delay: int = 120,
        request_timeout_ms: int = 120_000,
    ) -> None:
        """Initialize the GeminiProvider instance."""
        from google import genai
        from google.genai import types

        self.model_name = model_name
        self.tpm_limit = tpm_limit
        self._token_limiter = TokenWindowLimiter(tpm_limit) if tpm_limit else None
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay
        self._limiter = _shared_limiter(api_key, model_name, rpm_limit, rpm_reserve)
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=max(5_000, request_timeout_ms),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        self.wait_callback: Callable[[int, str], None] | None = None
        self.usage_callback: Callable[[LLMUsageRecord], None] | None = None
        self.usage_records: list[LLMUsageRecord] = []

    def _preflight_tokens(self, prompt: str, system_instruction: str) -> None:
        """Count the prompt's tokens and wait for room under GEMINI_TPM_LIMIT."""
        if not getattr(self, "_token_limiter", None):
            return
        started = time.monotonic()
        try:
            response = self._client.models.count_tokens(
                model=self.model_name,
                contents=f"{system_instruction}\n\n{prompt}",
            )
            self._record_auxiliary(COUNT_TOKENS_OPERATION, started, "succeeded")
        except Exception as exc:
            self._record_auxiliary(COUNT_TOKENS_OPERATION, started, "failed", type(exc).__name__)
            raise
        tokens = int(getattr(response, "total_tokens", 0) or 0)
        self._token_limiter.acquire(tokens, self.wait_callback)

    def _usage(self, response) -> dict[str, int]:
        """Read the token counters of optional Gemini usage metadata."""
        usage = getattr(response, "usage_metadata", None)

        def value(name: str) -> int:
            """Read one token counter from optional Gemini usage metadata."""
            return int(getattr(usage, name, 0) or 0) if usage else 0

        return {
            "prompt_tokens": value("prompt_token_count"),
            "candidate_tokens": value("candidates_token_count"),
            "thoughts_tokens": value("thoughts_token_count"),
            "cached_tokens": value("cached_content_token_count"),
            "total_tokens": value("total_token_count"),
        }

    def _invoke_structured(
        self, prompt: str, system_instruction: str, schema: type[BaseModel], temperature: float
    ):
        """Ask Gemini for JSON constrained by the sanitized schema."""
        from google.genai import types

        return self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=_gemini_response_schema(schema),
                temperature=temperature,
            ),
        )

    def _invoke_text(self, prompt: str, system_instruction: str, temperature: float):
        """Ask Gemini for free text."""
        from google.genai import types

        return self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
            ),
        )

    def _structured_payload(self, response):
        """Prefer the SDK's parsed object and fall back to the raw JSON text."""
        if response.parsed is not None:
            return response.parsed
        return response.text

    def _text_payload(self, response) -> str:
        """Return the text Gemini answered."""
        return response.text


class OpenAICompatibleError(Exception):
    """Carry an OpenAI-compatible HTTP failure with the fields the retry logic reads."""

    def __init__(self, status_code: int, message: str, retry_after: float | None = None) -> None:
        """Keep the status, a bounded message and the server's Retry-After, if any."""
        super().__init__(f"{status_code} {message}")
        self.status_code = status_code
        self.retry_after = retry_after


# Markers of a 429 that names a daily or monthly allowance rather than a per-minute one. Groq
# writes "tokens per day (TPD)" or "requests per day (RPD)"; OpenRouter "free-models-per-day";
# Mistral's monthly cap mentions the month.
_SPENT_QUOTA_MARKERS = ("per day", "per-day", "(tpd)", "(rpd)", "daily", "per month", "monthly")
# Provider replies to a response_format a model cannot honour.
_UNSUPPORTED_SCHEMA_MARKERS = ("response_format", "json_schema", "structured output")


class OpenAICompatibleProvider(_RecordingProvider):
    """Speak the OpenAI chat-completions protocol, as Groq and Mistral do, over httpx.

    Structured output asks for json_schema first. A model that rejects it with a 400 is asked
    again in json_object mode with the schema in the system instruction, and the provider keeps
    that mode for the rest of the process.
    """

    quota_recommendation = "Espera a que se restablezca el cupo o deja que la cadena siga."

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: str,
        *,
        label: str,
        rpm_limit: int = 30,
        rpm_reserve: int = 1,
        max_retries: int = 3,
        max_retry_delay: int = 120,
        request_timeout_ms: int = 120_000,
    ) -> None:
        """Initialize the provider for one base URL and model."""
        import httpx

        self.model_name = model_name
        self.provider_label = label
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay
        self.schema_mode = "json_schema"
        self._limiter = _shared_limiter(api_key, model_name, rpm_limit, rpm_reserve)
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=max(5_000, request_timeout_ms) / 1000,
        )
        self.wait_callback: Callable[[int, str], None] | None = None
        self.usage_callback: Callable[[LLMUsageRecord], None] | None = None
        self.usage_records: list[LLMUsageRecord] = []

    def _post(self, body: dict) -> dict:
        """POST one chat completion and raise OpenAICompatibleError on any HTTP failure."""
        response = self._client.post("/chat/completions", json=body)
        if response.status_code >= 400:
            retry_after = response.headers.get("retry-after")
            try:
                delay = float(retry_after) if retry_after else None
            except ValueError:
                delay = None
            raise OpenAICompatibleError(response.status_code, response.text[:600], delay)
        return response.json()

    def _body(self, system_instruction: str, prompt: str, temperature: float) -> dict:
        """Build the chat-completions body shared by both kinds of request."""
        return {
            "model": self.model_name,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
        }

    def _invoke_structured(
        self, prompt: str, system_instruction: str, schema: type[BaseModel], temperature: float
    ):
        """Ask for JSON in json_schema mode, dropping to json_object if the model refuses it."""
        json_schema = _gemini_response_schema(schema)
        if getattr(self, "schema_mode", "json_schema") == "json_schema":
            body = self._body(system_instruction, prompt, temperature)
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": json_schema, "strict": False},
            }
            try:
                return self._post(body)
            except OpenAICompatibleError as exc:
                text = str(exc).casefold()
                if exc.status_code != 400 or not any(
                    marker in text for marker in _UNSUPPORTED_SCHEMA_MARKERS
                ):
                    raise
                self.schema_mode = "json_object"
        system = (
            f"{system_instruction}\n\nReturn only one JSON object that matches this JSON "
            f"schema:\n{json.dumps(json_schema, ensure_ascii=False)}"
        )
        body = self._body(system, prompt, temperature)
        body["response_format"] = {"type": "json_object"}
        return self._post(body)

    def _invoke_text(self, prompt: str, system_instruction: str, temperature: float):
        """Ask for free text."""
        return self._post(self._body(system_instruction, prompt, temperature))

    def _structured_payload(self, response) -> str:
        """Return the JSON text of the first choice."""
        return self._text_payload(response)

    def _text_payload(self, response) -> str:
        """Return the content of the first choice, or an empty string."""
        choices = response.get("choices") or [{}]
        return (choices[0].get("message") or {}).get("content") or ""

    def _usage(self, response) -> dict[str, int]:
        """Read the OpenAI-style usage block into LLMUsageRecord fields."""
        usage = response.get("usage") or {}

        def value(block: dict, name: str) -> int:
            """Read one optional integer counter."""
            return int((block or {}).get(name) or 0)

        return {
            "prompt_tokens": value(usage, "prompt_tokens"),
            "candidate_tokens": value(usage, "completion_tokens"),
            "thoughts_tokens": value(usage.get("completion_tokens_details"), "reasoning_tokens"),
            "cached_tokens": value(usage.get("prompt_tokens_details"), "cached_tokens"),
            "total_tokens": value(usage, "total_tokens"),
        }

    def _retry_details(self, exc: Exception) -> dict[str, object]:
        """Add the server's Retry-After to the generic diagnostics."""
        details = retry_details(exc)
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is not None and details.get("retry_delay") is None:
            details["retry_delay"] = retry_after
        return details

    def _is_spent_quota(self, exc: Exception, details: dict) -> bool:
        """Recognize a daily or monthly cap from the text of the 429."""
        text = str(exc).casefold()
        return any(marker in text for marker in _SPENT_QUOTA_MARKERS)

    def _quota_error_type(self, exc: Exception, details: dict) -> type[ProviderError]:
        """File a spent allowance as a daily quota and any other final 429 as RPM."""
        return ProviderDailyQuotaError if self._is_spent_quota(exc, details) else GeminiRPMError

    def _safe_error(self, exc: Exception) -> ProviderError:
        """Classify a failure under this provider's name and without its credentials."""
        return ProviderError(
            f"{self.provider_label} no pudo completar la solicitud.",
            details={
                "exception_type": type(exc).__name__,
                **{
                    key: value
                    for key, value in retry_details(exc).items()
                    if value is not None and key != "status_name"
                },
            },
            recommendations=[
                f"Comprueba la clave y el modelo de {self.provider_label} en el .env."
            ],
        )


class _ProviderGroup:
    """Present several providers as one: one usage list and one pair of run callbacks.

    The pipeline reads usage_records and sets the callbacks on the provider it was given, so a
    group hands each assignment to every child; each record still names the model that answered.
    """

    def _children(self) -> list:
        """Return the providers this group speaks for."""
        raise NotImplementedError

    @property
    def usage_records(self) -> list[LLMUsageRecord]:
        """Return the usage list every child appends to."""
        return self._usage_records

    @usage_records.setter
    def usage_records(self, records: list[LLMUsageRecord]) -> None:
        """Replace the shared usage list in every child at once."""
        self._usage_records = records
        for child in self._children():
            child.usage_records = records

    @property
    def wait_callback(self) -> Callable[[int, str], None] | None:
        """Return the quota-wait callback every child reports to."""
        return self._wait_callback

    @wait_callback.setter
    def wait_callback(self, callback: Callable[[int, str], None] | None) -> None:
        """Hand the quota-wait callback to every child."""
        self._wait_callback = callback
        for child in self._children():
            child.wait_callback = callback

    @property
    def usage_callback(self) -> Callable[[LLMUsageRecord], None] | None:
        """Return the usage callback every child reports to."""
        return self._usage_callback

    @usage_callback.setter
    def usage_callback(self, callback: Callable[[LLMUsageRecord], None] | None) -> None:
        """Hand the usage callback to every child."""
        self._usage_callback = callback
        for child in self._children():
            child.usage_callback = callback


class RoutedProvider(_ProviderGroup):
    """Send the performance's calls to their own provider and every other call to the main one.

    The pipeline tags each call with its stage (call_context), so routing needs no agent to
    know about it.
    """

    def __init__(self, main, stage, *, stages: frozenset[str] = STAGE_MODEL_STAGES) -> None:
        """Wrap the main and performance providers and join their usage records."""
        self.main = main
        self.stage = stage
        self.stages = stages
        self.model_name = main.model_name
        self.stage_model_name = stage.model_name
        self._wait_callback = None
        self._usage_callback = None
        self.usage_records = []

    def _children(self) -> list:
        """Return the main and the performance providers."""
        return [self.main, self.stage]

    def provider_for_current_call(self):
        """Pick the provider for the call being made now, from the stage the pipeline declared."""
        stage, _ = current_call_context()
        return self.stage if stage in self.stages else self.main

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[T], profile: str
    ) -> T:
        """Generate a structured response with the provider this stage belongs to."""
        return self.provider_for_current_call().generate_structured(
            system_instruction=system_instruction, prompt=prompt, schema=schema, profile=profile
        )

    def generate_text(self, *, system_instruction: str, prompt: str, profile: str) -> str:
        """Generate free text with the provider this stage belongs to."""
        return self.provider_for_current_call().generate_text(
            system_instruction=system_instruction, prompt=prompt, profile=profile
        )


# Room left for the answer when a call's size is estimated before it is made; a ledger slot
# with a token cap is skipped unless the prompt plus this margin still fits.
_ESTIMATED_OUTPUT_TOKENS = 2_000


def _estimate_tokens(system_instruction: str, prompt: str) -> int:
    """Estimate a call's tokens from its characters, with room for the answer."""
    return (len(system_instruction) + len(prompt)) // 4 + _ESTIMATED_OUTPUT_TOKENS


class FailoverProvider(_ProviderGroup):
    """Try the slots of a provider chain in order, moving on when one's allowance is spent.

    The ledger skips a slot whose cap or declared exhaustion is known, so a spent quota costs
    no request to rediscover; a slot that answers with a daily or monthly 429 is marked out
    until its window resets and the same call is repeated on the next slot.
    """

    def __init__(self, entries: list[tuple[QuotaSlot, object]], ledger: QuotaLedger) -> None:
        """Wrap an ordered list of (slot, provider) pairs sharing one ledger."""
        if not entries:
            raise ValueError("A provider chain needs at least one slot")
        self.entries = entries
        self.ledger = ledger
        self.model_name = entries[0][1].model_name
        self._wait_callback = None
        self._usage_callback = None
        self.usage_records = []

    def _children(self) -> list:
        """Return the provider of every slot."""
        return [provider for _, provider in self.entries]

    def _record_spent(self, slot: QuotaSlot, before: int) -> None:
        """Charge the slot with the requests and tokens its provider recorded since before."""
        spent = [
            record
            for record in self.usage_records[before:]
            if record.operation != COUNT_TOKENS_OPERATION
        ]
        if spent:
            self.ledger.record(
                slot, requests=len(spent), tokens=sum(record.total_tokens for record in spent)
            )

    def _call(self, method: str, estimated_tokens: int, **kwargs):
        """Run one call on the first slot with allowance, failing over on a spent quota."""
        for index, (slot, provider) in enumerate(self.entries):
            if not self.ledger.available(slot, estimated_tokens):
                continue
            before = len(self.usage_records)
            try:
                return getattr(provider, method)(**kwargs)
            except ProviderDailyQuotaError as exc:
                self.ledger.mark_exhausted(slot, retry_after=exc.details.get("retry_delay"))
                following = next(
                    (
                        later.key
                        for later, _ in self.entries[index + 1 :]
                        if self.ledger.available(later, estimated_tokens)
                    ),
                    None,
                )
                if following and self.wait_callback:
                    self.wait_callback(1, f"{slot.key} agotado; sigo con {following}")
            finally:
                self._record_spent(slot, before)
        resets = [
            self.ledger.exhausted_until(slot) or self.ledger.resets_at(slot)
            for slot, _ in self.entries
        ]
        raise ProviderDailyQuotaError(
            "Todos los proveedores de la cadena agotaron su cupo.",
            details={
                "slots": [slot.key for slot, _ in self.entries],
                "next_reset": min(resets).isoformat(),
            },
            recommendations=["Espera al próximo reinicio o añade otro proveedor a ASG_LLM_CHAIN."],
        )

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[T], profile: str
    ) -> T:
        """Generate a structured response on the first slot with allowance."""
        return self._call(
            "generate_structured",
            _estimate_tokens(system_instruction, prompt),
            system_instruction=system_instruction,
            prompt=prompt,
            schema=schema,
            profile=profile,
        )

    def generate_text(self, *, system_instruction: str, prompt: str, profile: str) -> str:
        """Generate free text on the first slot with allowance."""
        return self._call(
            "generate_text",
            _estimate_tokens(system_instruction, prompt),
            system_instruction=system_instruction,
            prompt=prompt,
            profile=profile,
        )


def _chain_provider(entry: ChainEntry, settings: Settings):
    """Build the client of one chain slot."""
    shared = {
        "rpm_reserve": settings.rpm_reserve,
        "max_retries": settings.max_retries,
        "max_retry_delay": settings.max_retry_delay,
        "request_timeout_ms": settings.request_timeout_ms,
    }
    if entry.slot.provider == "gemini":
        return GeminiProvider(
            entry.api_key,
            entry.slot.model,
            rpm_limit=entry.rpm_limit,
            tpm_limit=settings.tpm_limit,
            **shared,
        )
    return OpenAICompatibleProvider(
        entry.api_key,
        entry.slot.model,
        entry.base_url,
        label=entry.label,
        rpm_limit=entry.rpm_limit,
        **shared,
    )


def provider_from_settings(settings: Settings):
    """Build the provider a run uses.

    Without ASG_LLM_CHAIN: one Gemini provider, or a routed pair when GEMINI_STAGE_MODEL,
    GEMINI_STAGE_API_KEY or GEMINI_STAGE_RPM_LIMIT make the performance differ; nothing else
    changes. With a chain: one FailoverProvider every call goes through, the performance
    included, whose second Gemini model (GEMINI_STAGE_MODEL) follows the main one, so the main
    model's quota is spent first, then the second's, then the rest of the chain.
    """
    if not settings.chain:
        shared = {
            "rpm_reserve": settings.rpm_reserve,
            "tpm_limit": settings.tpm_limit,
            "max_retries": settings.max_retries,
            "max_retry_delay": settings.max_retry_delay,
            "request_timeout_ms": settings.request_timeout_ms,
        }
        main = GeminiProvider(
            settings.api_key, settings.model, rpm_limit=settings.rpm_limit, **shared
        )
        if not settings.splits_stage:
            return main
        stage = GeminiProvider(
            settings.effective_stage_api_key,
            settings.effective_stage_model,
            rpm_limit=settings.effective_stage_rpm_limit,
            **shared,
        )
        return RoutedProvider(main, stage)
    entries = settings.quota_entries()
    return FailoverProvider(
        [(entry.slot, _chain_provider(entry, settings)) for entry in entries],
        QuotaLedger(settings.budget_path),
    )
