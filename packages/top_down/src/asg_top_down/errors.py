"""Public, structured, and safe errors for Top-Down production."""

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


class ArtifactValidationError(ASGError):
    """Represent ArtifactValidationError data and behavior."""

    code = "ARTIFACT_VALIDATION_FAILED"
    stage = "planning"

    def __init__(self, summary: str, *, stage: str = "planning", **kwargs) -> None:
        """Initialize the ArtifactValidationError instance."""
        super().__init__(summary, **kwargs)
        self.stage = stage


class PlotValidationError(ASGError):
    """Represent PlotValidationError data and behavior."""

    code = "PLOT_VALIDATION_FAILED"
    stage = "planning"


class GeminiRPMError(ProviderError):
    """Represent GeminiRPMError data and behavior."""

    code = "GEMINI_RPM_EXHAUSTED"


class GeminiTPMError(ProviderError):
    """Represent GeminiTPMError data and behavior."""

    code = "GEMINI_TPM_EXHAUSTED"


class GeminiDailyQuotaError(ProviderError):
    """Represent GeminiDailyQuotaError data and behavior."""

    code = "GEMINI_DAILY_QUOTA_EXHAUSTED"


class GeminiBillingQuotaError(ProviderError):
    """Represent GeminiBillingQuotaError data and behavior."""

    code = "GEMINI_BILLING_LIMIT_EXHAUSTED"
