"""Bounded, context-aware repair for the two optional guidance stages."""

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from ..runtime.errors import NON_DEGRADABLE_ERRORS
from ..runtime.provider import LanguageModelProvider

T = TypeVar("T", bound=BaseModel)


def request_validated(
    provider: LanguageModelProvider,
    *,
    instruction: str,
    prompt: str,
    schema: type[T],
    validate: Callable[[T], None],
    profile: str,
    rejected_drafts: list[dict] | None = None,
) -> tuple[T | None, list[str], int]:
    """Try a structured operation twice, recording safe errors and repairing context errors."""
    diagnostics: list[str] = []
    feedback = ""
    for attempt in range(1, 3):
        rejected = ""
        try:
            raw = provider.generate_structured(
                system_instruction=instruction,
                prompt=prompt + feedback,
                schema=schema,
                profile=profile,
            )
            result = schema.model_validate(raw)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            issue = f"structured_response_unavailable:{type(exc).__name__}"
        else:
            try:
                validate(result)
            except ValueError as exc:
                issue = str(exc)
                if rejected_drafts is not None:
                    rejected_drafts.append(result.model_dump(mode="json"))
                rejected = "\n\nPREVIOUS GUIDANCE (data to correct):\n" + result.model_dump_json(
                    indent=2
                )
            else:
                return result, diagnostics, attempt
        diagnostics.append(issue)
        feedback = (
            f"\n\nGUIDANCE CORRECTION:\n{issue}{rejected}"
            "\nReturn a complete corrected response, preserving valid choices where possible."
        )
    return None, diagnostics, 2
