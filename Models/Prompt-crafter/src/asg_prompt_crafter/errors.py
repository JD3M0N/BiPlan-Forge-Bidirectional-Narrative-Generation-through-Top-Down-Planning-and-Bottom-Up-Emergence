"""Errores públicos del módulo Prompt-crafter."""

class PromptCrafterError(Exception):
    """Error base controlado por el módulo."""

class ConfigurationError(PromptCrafterError):
    """La configuración necesaria no está disponible."""

class ProviderError(PromptCrafterError):
    """El proveedor de lenguaje no pudo completar la solicitud."""

class EmptyResponseError(ProviderError):
    """El proveedor devolvió una respuesta vacía."""

class StructuredResponseError(ProviderError):
    """La respuesta no satisface el contrato estructurado."""
