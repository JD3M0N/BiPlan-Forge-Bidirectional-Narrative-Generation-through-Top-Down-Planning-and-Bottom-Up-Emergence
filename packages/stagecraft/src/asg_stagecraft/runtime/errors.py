"""Public, structured, and safe errors for Stagecraft production."""

from typing import Any


class ASGError(Exception):
    """Represent ASGError data and behavior."""

    code = "ASG_ERROR"
    stage = "unknown"

    def __init__(
        self,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        recommendations: list[str] | None = None,
    ) -> None:
        """Initialize the ASGError instance."""
        super().__init__(summary)
        self.summary = summary
        self.details = details or {}
        self.recommendations = recommendations or []
        self.run_id: str | None = None

    def public_message(self) -> str:
        """Handle the public message operation for ASGError."""
        lines = [self.summary, f"Código: {self.code}."]
        if self.recommendations:
            lines.append("Sugerencia: " + self.recommendations[0])
        if self.run_id:
            lines.append(f"Ejecución: {self.run_id}.")
        return "\n".join(lines)


class ConfigurationError(ASGError):
    """Represent ConfigurationError data and behavior."""

    code = "CONFIGURATION_ERROR"
    stage = "configuration"


class ProviderError(ASGError):
    """Represent ProviderError data and behavior."""

    code = "PROVIDER_ERROR"
    stage = "provider"


class EmptyResponseError(ProviderError):
    """Represent EmptyResponseError data and behavior."""

    code = "PROVIDER_EMPTY_RESPONSE"


class StructuredResponseError(ProviderError):
    """Represent StructuredResponseError data and behavior."""

    code = "PROVIDER_INVALID_SCHEMA"


class PlotValidationError(ASGError):
    """Represent PlotValidationError data and behavior."""

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
    """Represent RunArtifactError data and behavior."""

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
    """Represent GeminiRPMError data and behavior."""

    code = "GEMINI_RPM_EXHAUSTED"


class GeminiTPMError(ProviderError):
    """Represent GeminiTPMError data and behavior."""

    code = "GEMINI_TPM_EXHAUSTED"


class ProviderDailyQuotaError(ProviderError):
    """Signal a provider whose daily or monthly allowance is spent, so a chain can move on."""

    code = "PROVIDER_DAILY_QUOTA_EXHAUSTED"


class GeminiDailyQuotaError(ProviderDailyQuotaError):
    """Represent GeminiDailyQuotaError data and behavior."""

    code = "GEMINI_DAILY_QUOTA_EXHAUSTED"


class GeminiBillingQuotaError(ProviderError):
    """Represent GeminiBillingQuotaError data and behavior."""

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
