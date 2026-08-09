"""Errores públicos, estructurados y seguros del sistema ASG."""

from typing import Any


class ASGError(Exception):
    """Error esperado y presentable al usuario."""

    code = "ASG_ERROR"
    stage = "unknown"

    def __init__(self, summary: str, *, details: dict[str, Any] | None = None,
                 recommendations: list[str] | None = None) -> None:
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
    """La configuración local no permite ejecutar el pipeline."""
    code = "CONFIGURATION_ERROR"
    stage = "configuration"


class ProviderError(ASGError):
    """El proveedor de lenguaje no pudo generar una respuesta válida."""
    code = "PROVIDER_ERROR"
    stage = "provider"


class EmptyResponseError(ProviderError):
    """El proveedor devolvió una respuesta vacía."""
    code = "PROVIDER_EMPTY_RESPONSE"


class StructuredResponseError(ProviderError):
    """La respuesta no satisface el esquema solicitado."""
    code = "PROVIDER_INVALID_SCHEMA"


class StorylinePlanningError(ASGError):
    code = "STORYLINE_PLANNING_FAILED"
    stage = "director"


class ChapterComplianceError(ASGError):
    code = "CHAPTER_COMPLIANCE_FAILED"
    stage = "scenes"

    def public_message(self) -> str:
        missing_nodes = ", ".join(self.details.get("missing_node_ids", [])) or "ninguno"
        missing_goals = ", ".join(self.details.get("missing_goals", [])) or "ninguno"
        lines = [
            self.summary,
            f"Nodos pendientes: {missing_nodes}.",
            f"Goals pendientes: {missing_goals}.",
            f"Se realizaron {self.details.get('attempts', 3)} intentos. Código: {self.code}.",
        ]
        if self.run_id:
            lines.append(f"Los detalles quedaron guardados en {self.run_id}.")
        return "\n".join(lines)


class FreytagValidationError(ASGError):
    code = "FREYTAG_VALIDATION_FAILED"
    stage = "review"


class FinalLengthError(ASGError):
    code = "FINAL_LENGTH_FAILED"
    stage = "editing"

    def public_message(self) -> str:
        lines = [
            self.summary,
            f"No fue posible ajustarla después de {self.details.get('attempts', 3) - 1} correcciones.",
            f"Código: {self.code}.",
        ]
        if self.run_id:
            lines.append(f"Ejecución: {self.run_id}.")
        return "\n".join(lines)


class DeliveryError(ASGError):
    code = "DELIVERY_FAILED"
    stage = "delivery"


class GeminiRPMError(ProviderError):
    code = "GEMINI_RPM_EXHAUSTED"


class GeminiTPMError(ProviderError):
    code = "GEMINI_TPM_EXHAUSTED"


class GeminiDailyQuotaError(ProviderError):
    code = "GEMINI_DAILY_QUOTA_EXHAUSTED"


class GeminiBillingQuotaError(ProviderError):
    code = "GEMINI_BILLING_LIMIT_EXHAUSTED"


class QueueRecoveryError(ASGError):
    code = "CHECKPOINT_RECOVERY_FAILED"
    stage = "queue"
