"""Public, structured, and safe errors for Stagecraft production."""

from typing import Any


class ASGError(Exception):
    """Base of every Stagecraft error; subclasses fix a stable code and the stage that failed."""

    code = "ASG_ERROR"
    stage = "unknown"

    def __init__(
        self,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        recommendations: list[str] | None = None,
    ) -> None:
        """Keep a summary, optional details and recommendations; the run id is set later."""
        super().__init__(summary)
        self.summary = summary
        self.details = details or {}
        self.recommendations = recommendations or []
        self.run_id: str | None = None

    def public_message(self) -> str:
        """Render the Spanish message shown to the user, with code, first hint and run id."""
        lines = [self.summary, f"Código: {self.code}."]
        if self.recommendations:
            lines.append("Sugerencia: " + self.recommendations[0])
        if self.run_id:
            lines.append(f"Ejecución: {self.run_id}.")
        return "\n".join(lines)


class ConfigurationError(ASGError):
    """Signal missing or invalid local configuration, such as an absent API key."""

    code = "CONFIGURATION_ERROR"
    stage = "configuration"


class ProviderError(ASGError):
    """Base of failures raised while calling a language model provider."""

    code = "PROVIDER_ERROR"
    stage = "provider"


class EmptyResponseError(ProviderError):
    """Signal a provider reply with no usable text."""

    code = "PROVIDER_EMPTY_RESPONSE"


class StructuredResponseError(ProviderError):
    """Signal a provider reply that does not parse into the requested schema."""

    code = "PROVIDER_INVALID_SCHEMA"


class PlotValidationError(ASGError):
    """Signal a plan that fails the structural checks after its repair attempts."""

    code = "PLOT_VALIDATION_FAILED"
    stage = "planning"


class ScriptValidationError(ASGError):
    """Raised when no proposed act satisfies script.py's staging rules within its attempts."""

    code = "SCRIPT_VALIDATION_FAILED"
    stage = "drafting"


class StagePerformanceError(ASGError):
    """Raised when a scene cannot be performed at all, so no log exists to narrate from."""

    code = "STAGE_PERFORMANCE_FAILED"
    stage = "performance"


class RunArtifactError(ASGError):
    """Signal a stored run whose metadata or artifacts cannot be read or are incompatible."""

    code = "RUN_ARTIFACT_INVALID"
    stage = "loading"


class RunInterruptedError(ASGError):
    """Signal a run the process abandoned, such as a keyboard interrupt or a forced exit."""

    code = "RUN_INTERRUPTED"
    stage = "unknown"


class RunCancelledError(ASGError):
    """Signal a run its caller asked to stop, raised by the pipeline at its next agent call.

    Surfaces pass should_cancel to generate() instead of raising from a progress callback: a
    callback can fire inside the provider's retry loop, where any exception is rewrapped as a
    degradable provider error, and again while a failure is being recorded.
    """

    code = "RUN_CANCELLED"
    stage = "unknown"


class GeminiRPMError(ProviderError):
    """Signal that the Gemini requests-per-minute allowance is exhausted."""

    code = "GEMINI_RPM_EXHAUSTED"


class GeminiTPMError(ProviderError):
    """Signal that the Gemini tokens-per-minute allowance is exhausted."""

    code = "GEMINI_TPM_EXHAUSTED"


class ProviderDailyQuotaError(ProviderError):
    """Signal a provider whose daily or monthly allowance is spent, so a chain can move on."""

    code = "PROVIDER_DAILY_QUOTA_EXHAUSTED"


class ProviderUnavailableError(ProviderError):
    """Signal a provider that refuses this caller outright (401 or 403), so a chain can skip it.

    Groq answers 403 "Access denied. Please check your network settings." to networks it
    blocks: the key is fine and no retry helps, but before 7.9.1 the chain treated it like any
    other failure and the run died there with Mistral still untried.
    """

    code = "PROVIDER_UNAVAILABLE"


class ProviderOverloadedError(ProviderError):
    """Signal a provider that kept answering 5xx through every retry, so a chain can move on.

    Found in the 7.12 validation run: gemini-3.5-flash-lite answered 503 and 504 to most calls
    for minutes while the next slot of the chain, another model with its own capacity, sat
    idle. Unlike a spent quota, it says nothing about the next call, so nothing is marked out.
    """

    code = "PROVIDER_OVERLOADED"


class GeminiDailyQuotaError(ProviderDailyQuotaError):
    """Signal that the Gemini daily request allowance is spent."""

    code = "GEMINI_DAILY_QUOTA_EXHAUSTED"


class GeminiBillingQuotaError(ProviderError):
    """Signal that the Gemini billing or spending limit is reached."""

    code = "GEMINI_BILLING_LIMIT_EXHAUSTED"


# Errors that must always abort the pipeline instead of being degraded to a warning. A
# cancellation belongs here: otherwise a stage that degrades would swallow it and carry on.
NON_DEGRADABLE_ERRORS = (
    RunCancelledError,
    ConfigurationError,
    GeminiRPMError,
    GeminiTPMError,
    ProviderDailyQuotaError,
    GeminiBillingQuotaError,
)
