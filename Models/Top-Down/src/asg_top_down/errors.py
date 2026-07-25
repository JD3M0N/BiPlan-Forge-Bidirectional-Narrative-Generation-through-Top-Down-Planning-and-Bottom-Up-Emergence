"""Errores públicos del sistema ASG."""


class ASGError(Exception):
    """Error esperado y presentable al usuario."""


class ConfigurationError(ASGError):
    """La configuración local no permite ejecutar el pipeline."""


class ProviderError(ASGError):
    """El proveedor de lenguaje no pudo generar una respuesta válida."""


class EmptyResponseError(ProviderError):
    """El proveedor devolvió una respuesta vacía."""


class StructuredResponseError(ProviderError):
    """La respuesta no satisface el esquema solicitado."""

