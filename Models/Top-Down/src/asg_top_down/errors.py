"""Public, structured, and safe errors for Top-Down production."""

from typing import Any


class ASGError(Exception):
    code = "ASG_ERROR"
    stage = "unknown"

    def __init__(
        self,
        summary: str,
        *,
        details: dict[str, Any] | None = None,
        recommendations: list[str] | None = None,
    ) -> None:
        super().__init__(summary)
        self.summary = summary
        self.details = details or {}
        self.recommendations = recommendations or []
        self.run_id: str | None = None

    def public_message(self) -> str:
        lines = [self.summary, f"Código: {self.code}."]
        if self.recommendations:
            lines.append("Sugerencia: " + self.recommendations[0])
        if self.run_id:
            lines.append(f"Ejecución: {self.run_id}.")
        return "\n".join(lines)


class ConfigurationError(ASGError):
    code = "CONFIGURATION_ERROR"
    stage = "configuration"


class ProviderError(ASGError):
    code = "PROVIDER_ERROR"
    stage = "provider"


class EmptyResponseError(ProviderError):
    code = "PROVIDER_EMPTY_RESPONSE"


class StructuredResponseError(ProviderError):
    code = "PROVIDER_INVALID_SCHEMA"


class ArtifactValidationError(ASGError):
    code = "ARTIFACT_VALIDATION_FAILED"
    stage = "planning"

    def __init__(self, summary: str, *, stage: str = "planning", **kwargs) -> None:
        super().__init__(summary, **kwargs)
        self.stage = stage


class StorylinePlanningError(ASGError):
    code = "STORYLINE_PLANNING_FAILED"
    stage = "storyline"


class GeminiRPMError(ProviderError):
    code = "GEMINI_RPM_EXHAUSTED"


class GeminiTPMError(ProviderError):
    code = "GEMINI_TPM_EXHAUSTED"


class GeminiDailyQuotaError(ProviderError):
    code = "GEMINI_DAILY_QUOTA_EXHAUSTED"


class GeminiBillingQuotaError(ProviderError):
    code = "GEMINI_BILLING_LIMIT_EXHAUSTED"
