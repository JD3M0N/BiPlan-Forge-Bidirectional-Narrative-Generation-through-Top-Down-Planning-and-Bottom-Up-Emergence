"""Language-model provider abstraction and Gemini implementation."""

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
from .config import Settings
from .errors import (
    EmptyResponseError,
    GeminiBillingQuotaError,
    GeminiDailyQuotaError,
    GeminiRPMError,
    GeminiTPMError,
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
_LIMITERS: dict[tuple[int, int], SlidingWindowLimiter] = {}
_LIMITERS_LOCK = threading.Lock()
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
        recommendation = "Comprueba GEMINI_MODEL."
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


class GeminiProvider:
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
        capacity = max(1, rpm_limit - rpm_reserve)
        with _LIMITERS_LOCK:
            self._limiter = _LIMITERS.setdefault((capacity, 60), SlidingWindowLimiter(capacity))
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

    def _temperature(self, profile: str) -> float:
        """Look up the configured temperature for an explicit generation profile."""
        try:
            return float(_DEFAULT_GENERATION_PROFILES[profile])
        except KeyError as exc:
            raise ValueError(f"Unknown generation profile: {profile!r}") from exc

    def _preflight_tokens(self, prompt: str, system_instruction: str) -> None:
        """Handle the preflight tokens operation for GeminiProvider."""
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
        usage = getattr(response, "usage_metadata", None)

        def value(name: str) -> int:
            """Read one token counter from optional Gemini usage metadata."""
            return int(getattr(usage, name, 0) or 0) if usage else 0

        stage, agent = current_call_context()
        record = LLMUsageRecord(
            call_id=call_id,
            operation=operation,
            stage=stage or operation,
            agent=agent,
            attempt=attempt + 1,
            status="succeeded",
            model=self.model_name,
            timestamp=datetime.now(UTC),
            duration_seconds=duration,
            prompt_tokens=value("prompt_token_count"),
            candidate_tokens=value("candidates_token_count"),
            thoughts_tokens=value("thoughts_token_count"),
            cached_tokens=value("cached_content_token_count"),
            total_tokens=value("total_token_count"),
            retries=attempt,
            wait_seconds=waited,
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
                details = retry_details(exc)
                status = details.get("status")
                self._record_failure(
                    operation,
                    call_id,
                    attempt,
                    elapsed,
                    waited,
                    str(status or type(exc).__name__),
                )
                quota_id = str(details.get("quota_id") or "").casefold()
                metric = str(details.get("metric") or "").casefold()
                permanent_quota = status == 429 and any(
                    marker in quota_id or marker in metric
                    for marker in ("day", "daily", "billing", "spend")
                )
                transient = (
                    status in {408, 429}
                    or (isinstance(status, int) and 500 <= status < 600)
                    or _is_transient_transport_error(exc)
                )
                if permanent_quota or not transient or attempt >= max_retries:
                    if status == 429:
                        error_type = _quota_error_type(exc, details)
                        raise error_type(
                            f"Gemini agotó la cuota para {self.model_name}.",
                            details={
                                **details,
                                "model": self.model_name,
                                "attempts": attempt + 1,
                                "retries": attempt,
                            },
                            recommendations=[
                                "Espera a que se restablezca la cuota o revisa tu plan en "
                                "AI Studio."
                            ],
                        ) from exc
                    raise
                delay = retry_delay(attempt + 1, details)
                if delay > getattr(self, "max_retry_delay", 120):
                    raise GeminiRPMError(
                        "Gemini indicó una espera superior al máximo configurado.",
                        details={**details, "model": self.model_name},
                        recommendations=["Reanuda el trabajo cuando se restablezca la cuota."],
                    ) from exc
                countdown_wait(delay, "reintento solicitado por Gemini", callback)
                pending_wait = delay

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[T], profile: str
    ) -> T:
        """Generate structured."""
        from google.genai import types

        temperature = self._temperature(profile)
        validation_retries = _STRUCTURED_VALIDATION_RETRIES
        current_prompt = prompt
        last_errors: list[dict[str, str]] = []
        for validation_attempt in range(validation_retries + 1):
            try:
                self._preflight_tokens(current_prompt, system_instruction)

                def invoke(prompt_snapshot: str = current_prompt):
                    """Request structured output with this attempt's bound prompt."""
                    return self._client.models.generate_content(
                        model=self.model_name,
                        contents=prompt_snapshot,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            response_schema=_gemini_response_schema(schema),
                            temperature=temperature,
                        ),
                    )

                response = self._generate(
                    f"structured:{schema.__name__}",
                    invoke,
                )
                if response.parsed is not None:
                    return schema.model_validate(response.parsed)
                if not response.text:
                    raise EmptyResponseError("Gemini devolvió una respuesta vacía.")
                return schema.model_validate_json(response.text)
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
                        f"Gemini devolvió datos incompatibles con {schema.__name__}.",
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
                raise _safe_provider_error(exc) from exc
        raise AssertionError("structured validation loop ended unexpectedly")

    def generate_text(self, *, system_instruction: str, prompt: str, profile: str) -> str:
        """Generate text."""
        from google.genai import types

        temperature = self._temperature(profile)
        try:
            self._preflight_tokens(prompt, system_instruction)

            def invoke():
                """Request free-form text from Gemini with the bound prompt."""
                return self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=temperature,
                    ),
                )

            response = self._generate("text", invoke)
            text = response.text
            if not text or not text.strip():
                raise EmptyResponseError("Gemini devolvió una respuesta vacía.")
            return text.strip()
        except ProviderError:
            raise
        except Exception as exc:
            raise _safe_provider_error(exc) from exc


def provider_from_settings(settings: Settings) -> GeminiProvider:
    """Build a GeminiProvider from loaded Stagecraft settings."""
    return GeminiProvider(
        settings.api_key,
        settings.model,
        rpm_limit=settings.rpm_limit,
        rpm_reserve=settings.rpm_reserve,
        tpm_limit=settings.tpm_limit,
        max_retries=settings.max_retries,
        max_retry_delay=settings.max_retry_delay,
        request_timeout_ms=settings.request_timeout_ms,
    )
