"""Abstracción del proveedor LLM e implementación para Gemini."""

from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from .errors import EmptyResponseError, ProviderError, StructuredResponseError

T = TypeVar("T", bound=BaseModel)


class LanguageModelProvider(Protocol):
    model_name: str

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[T]
    ) -> T: ...

    def generate_text(self, *, system_instruction: str, prompt: str) -> str: ...


class GeminiProvider:
    """Adaptador pequeño que contiene todo el acoplamiento con google-genai."""

    def __init__(self, api_key: str, model_name: str) -> None:
        from google import genai

        self.model_name = model_name
        self._client = genai.Client(api_key=api_key)

    def generate_structured(
        self, *, system_instruction: str, prompt: str, schema: type[T]
    ) -> T:
        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            if response.parsed is not None:
                return schema.model_validate(response.parsed)
            if not response.text:
                raise EmptyResponseError("Gemini devolvió una respuesta vacía.")
            return schema.model_validate_json(response.text)
        except (EmptyResponseError, StructuredResponseError):
            raise
        except ValidationError as exc:
            raise StructuredResponseError(
                f"Gemini devolvió datos incompatibles con {schema.__name__}."
            ) from exc
        except Exception as exc:
            raise ProviderError(f"Falló la solicitud a Gemini: {exc}") from exc

    def generate_text(self, *, system_instruction: str, prompt: str) -> str:
        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.8,
                ),
            )
            text = response.text
            if not text or not text.strip():
                raise EmptyResponseError("Gemini devolvió una respuesta vacía.")
            return text.strip()
        except EmptyResponseError:
            raise
        except Exception as exc:
            raise ProviderError(f"Falló la solicitud a Gemini: {exc}") from exc

