"""Abstracción del proveedor LLM e implementación para Gemini."""

from datetime import datetime, timezone
import json
import threading
import time
import uuid
from typing import Callable, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .errors import (
    EmptyResponseError, GeminiBillingQuotaError, GeminiDailyQuotaError,
    GeminiRPMError, GeminiTPMError,
    ProviderError, StructuredResponseError,
)
from .quota import SlidingWindowLimiter, TokenWindowLimiter, countdown_wait, retry_delay, retry_details
from .schemas import LLMUsageRecord

T = TypeVar("T", bound=BaseModel)
_LIMITERS: dict[tuple[int, int], SlidingWindowLimiter] = {}
_LIMITERS_LOCK = threading.Lock()


def _safe_provider_error(exc: Exception) -> ProviderError:
    """Classify provider failures without exposing request or credential data."""
    message = str(exc).casefold()
    if any(token in message for token in ("api key", "unauth", "permission", "401", "403")):
        summary = "Gemini rechazó la autenticación o los permisos configurados."
        recommendation = "Comprueba GEMINI_API_KEY y el acceso al modelo seleccionado."
    elif any(token in message for token in ("quota", "rate limit", "resource_exhausted", "429")):
        summary = "Gemini rechazó la solicitud por cuota o límite de uso."
        recommendation = "Espera unos minutos o revisa la cuota del proyecto de Gemini."
    elif isinstance(exc, (OSError, ConnectionError, TimeoutError)) or any(
        token in message for token in ("timeout", "timed out", "network", "connection", "dns", "sin red")
    ):
        summary = "No fue posible comunicarse con Gemini."
        recommendation = "Comprueba la conexión y vuelve a intentarlo."
    else:
        summary = "Gemini no pudo completar la solicitud."
        recommendation = "Vuelve a intentarlo y consulta el registro local si persiste."
    return ProviderError(
        summary, details={"exception_type": type(exc).__name__},
        recommendations=[recommendation],
    )


class LanguageModelProvider(Protocol):
    model_name: str

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[T]
    ) -> T: ...

    def generate_text(self, *, system_instruction: str, prompt: str) -> str: ...

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class GeminiProvider:
    """Adaptador pequeño que contiene todo el acoplamiento con google-genai."""

    def __init__(self, api_key: str, model_name: str, *, rpm_limit: int = 15,
                 rpm_reserve: int = 1, tpm_limit: int = 0,
                 max_retries: int = 3, max_retry_delay: int = 120,
                 embedding_model: str = "gemini-embedding-2",
                 generation_profiles: dict[str, float] | None = None) -> None:
        from google import genai
        from google.genai import types

        self.model_name = model_name
        self.embedding_model_name = embedding_model
        self.tpm_limit = tpm_limit
        self._token_limiter = TokenWindowLimiter(tpm_limit) if tpm_limit else None
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay
        self.structured_validation_retries = 1
        capacity = max(1, rpm_limit - rpm_reserve)
        with _LIMITERS_LOCK:
            self._limiter = _LIMITERS.setdefault((capacity, 60), SlidingWindowLimiter(capacity))
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
        self.wait_callback: Callable[[int, str], None] | None = None
        self.usage_callback: Callable[[LLMUsageRecord], None] | None = None
        self.usage_records: list[LLMUsageRecord] = []
        defaults = {
            "extraction": 0.15, "review": 0.2, "planning": 0.5,
            "proposal": 0.85, "prose": 0.9, "rewrite": 0.35,
        }
        self.generation_profiles = {**defaults, **(generation_profiles or {})}

    def _temperature(self, operation: str, system_instruction: str = "") -> float:
        text = f"{operation} {system_instruction}".casefold()
        if "rewrite" in text:
            profile = "rewrite"
        elif any(word in text for word in ("review", "critic", "analyst")):
            profile = "review" if "analyst" not in text else "extraction"
        elif any(word in text for word in ("proposal", "plotnodeproposal", "chapter body")):
            profile = "proposal"
        elif operation == "text":
            profile = "prose"
        else:
            profile = "planning"
        defaults = {
            "extraction": 0.15, "review": 0.2, "planning": 0.5,
            "proposal": 0.85, "prose": 0.9, "rewrite": 0.35,
        }
        return float(getattr(self, "generation_profiles", defaults).get(profile, defaults[profile]))

    def _embed(self, texts: list[str], prefix: str) -> list[list[float]]:
        """Embed a batch using the asymmetric retrieval format recommended by Gemini."""
        started = time.monotonic()
        try:
            contents = [f"{prefix}{text}" for text in texts]
            # Embeddings 2 aggregates multiple contents into one multimodal vector;
            # submit text documents independently so each catalog row keeps its vector.
            if self.embedding_model_name.endswith("-2") and len(contents) > 1:
                return [self._embed([content.removeprefix(prefix)], prefix)[0] for content in contents]
            response = self._client.models.embed_content(
                model=self.embedding_model_name, contents=contents,
            )
            self._record_auxiliary(
                f"embedding:{self.embedding_model_name}", started, "succeeded",
            )
            embeddings = getattr(response, "embeddings", None)
            if embeddings is None:
                single = getattr(response, "embedding", None)
                embeddings = [single] if single is not None else []
            return [list(item.values) for item in embeddings]
        except Exception as exc:
            self._record_auxiliary(
                f"embedding:{self.embedding_model_name}", started, "failed",
                type(exc).__name__,
            )
            raise _safe_provider_error(exc) from exc

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "task: search result | query: ")[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "title: narrative schema | text: ")

    def _preflight_tokens(self, prompt: str, system_instruction: str) -> None:
        if not getattr(self, "_token_limiter", None):
            return
        started = time.monotonic()
        try:
            response = self._client.models.count_tokens(
                model=self.model_name,
                contents=f"{system_instruction}\n\n{prompt}",
            )
            self._record_auxiliary("count_tokens", started, "succeeded")
        except Exception as exc:
            self._record_auxiliary("count_tokens", started, "failed", type(exc).__name__)
            raise
        tokens = int(getattr(response, "total_tokens", 0) or 0)
        self._token_limiter.acquire(tokens, self.wait_callback)

    def _emit_record(self, record: LLMUsageRecord) -> None:
        if not hasattr(self, "usage_records"):
            self.usage_records = []
        self.usage_records.append(record)
        callback = getattr(self, "usage_callback", None)
        if callback:
            callback(record)

    def _record_auxiliary(self, operation: str, started: float,
                          status: str, error_code: str | None = None) -> None:
        self._emit_record(LLMUsageRecord(
            call_id=uuid.uuid4().hex, operation=operation, stage=operation,
            attempt=1, status=status, error_code=error_code,
            model=(self.embedding_model_name if operation.startswith("embedding:")
                   else self.model_name),
            timestamp=datetime.now(timezone.utc),
            duration_seconds=time.monotonic() - started,
        ))

    def _record(self, response, operation: str, started: float, retries: int, waited: float) -> None:
        usage = getattr(response, "usage_metadata", None)
        value = lambda name: int(getattr(usage, name, 0) or 0) if usage else 0
        record = LLMUsageRecord(
            call_id=uuid.uuid4().hex, operation=operation, stage=operation,
            attempt=retries + 1, status="succeeded", model=self.model_name,
            timestamp=datetime.now(timezone.utc),
            duration_seconds=time.monotonic() - started,
            prompt_tokens=value("prompt_token_count"),
            candidate_tokens=value("candidates_token_count"),
            thoughts_tokens=value("thoughts_token_count"),
            cached_tokens=value("cached_content_token_count"),
            total_tokens=value("total_token_count"), retries=retries,
            wait_seconds=waited,
        )
        self._emit_record(record)

    def _record_failure(self, operation: str, started: float, attempt: int,
                        waited: float, error_code: str) -> None:
        self._emit_record(LLMUsageRecord(
            call_id=uuid.uuid4().hex, operation=operation, stage=operation,
            attempt=attempt + 1, status="failed", error_code=error_code,
            model=self.model_name, timestamp=datetime.now(timezone.utc),
            duration_seconds=time.monotonic() - started, wait_seconds=waited,
            retries=attempt,
        ))

    def _generate(self, operation: str, invoke):
        started, waited = time.monotonic(), 0.0
        max_retries = getattr(self, "max_retries", 1)
        limiter = getattr(self, "_limiter", None)
        callback = getattr(self, "wait_callback", None)
        if not hasattr(self, "usage_records"):
            self.usage_records = []
        # GEMINI_MAX_RETRIES describes retries after the initial request.
        for attempt in range(max_retries + 1):
            if limiter:
                waited += limiter.acquire(callback)
            try:
                response = invoke()
                self._record(response, operation, started, attempt, waited)
                return response
            except Exception as exc:
                details = retry_details(exc)
                status = details.get("status")
                self._record_failure(operation, started, attempt, waited, str(status or type(exc).__name__))
                quota_id = str(details.get("quota_id") or "").casefold()
                metric = str(details.get("metric") or "").casefold()
                permanent_quota = status == 429 and any(
                    marker in quota_id or marker in metric
                    for marker in ("day", "daily", "billing", "spend")
                )
                transient = status in {408, 429} or (isinstance(status, int) and 500 <= status < 600)
                if permanent_quota or not transient or attempt >= max_retries:
                    if status == 429:
                        metric = str(details.get("metric") or "")
                        quota_id = str(details.get("quota_id") or "")
                        error_type = GeminiTPMError if "token" in metric.casefold() else GeminiRPMError
                        if "day" in quota_id.casefold() or "daily" in metric.casefold():
                            error_type = GeminiDailyQuotaError
                        if "spend" in str(exc).casefold() or "billing" in str(exc).casefold():
                            error_type = GeminiBillingQuotaError
                        raise error_type(
                            f"Gemini agotó la cuota para {self.model_name}.",
                            details={**details, "model": self.model_name, "attempts": attempt + 1,
                                     "retries": attempt},
                            recommendations=["Espera a que se restablezca la cuota o revisa tu plan en AI Studio."],
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
                waited += delay

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[T]
    ) -> T:
        from google.genai import types

        validation_retries = max(0, getattr(self, "structured_validation_retries", 1))
        current_prompt = prompt
        last_errors: list[dict[str, str]] = []
        for validation_attempt in range(validation_retries + 1):
            try:
                self._preflight_tokens(current_prompt, system_instruction)
                response = self._generate(
                    f"structured:{schema.__name__}",
                    lambda: self._client.models.generate_content(
                        model=self.model_name, contents=current_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json", response_schema=schema,
                            temperature=self._temperature(schema.__name__, system_instruction),
                        ),
                    ),
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
                    }
                    for error in exc.errors(include_url=False, include_context=False, include_input=False)
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

    def generate_text(self, *, system_instruction: str, prompt: str) -> str:
        from google.genai import types

        try:
            self._preflight_tokens(prompt, system_instruction)
            response = self._generate(
                "text",
                lambda: self._client.models.generate_content(
                    model=self.model_name, contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=self._temperature("text", system_instruction),
                    ),
                ),
            )
            text = response.text
            if not text or not text.strip():
                raise EmptyResponseError("Gemini devolvió una respuesta vacía.")
            return text.strip()
        except ProviderError:
            raise
        except Exception as exc:
            raise _safe_provider_error(exc) from exc
