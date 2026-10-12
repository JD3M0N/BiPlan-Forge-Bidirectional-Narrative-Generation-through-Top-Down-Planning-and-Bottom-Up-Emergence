"""Independent catalog types shared by artifacts and narrative planning."""

import re
import unicodedata
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


def slug_id(value: object) -> object:
    """Turn a near-miss id into its one valid form; valid ids and non-strings pass untouched.

    Gemini does not enforce the schema's pattern: a 7.10 run died at the world stage because a
    location id came back with capitals or accents twice in a row. "Sala Del Trono" has exactly
    one correct reading, so it is normalized rather than rejected.
    """
    if not isinstance(value, str) or re.fullmatch(ID_PATTERN, value):
        return value
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9_-]+", "_", ascii_text.lower()).strip("_-")
    return slug or value


# Every id a model writes. The pattern still travels in the JSON schema; the validator only
# rescues values that would have failed it. Field goes first: placed after the validator,
# pydantic drops the pattern from the schema sent to the model.
ModelId = Annotated[str, Field(pattern=ID_PATTERN), BeforeValidator(slug_id)]


class GuidanceStrategy(StrEnum):
    """Select the preserved baseline or the experimental compositional guide."""

    HYBRID_V1 = "hybrid_v1"
    COMPOSITIONAL_V2 = "compositional_v2"


class Layer(StrEnum):
    """Describe typical narrative scope; compositional guidance treats it as advisory."""

    MACROPLOT = "macroplot"
    SUBPLOT = "subplot"


class FunctionalRole(StrEnum):
    """Name what a character does with respect to the focal goal, not who they are."""

    SUBJECT = "subject"
    OPPONENT = "opponent"
    HELPER = "helper"
    DONOR = "donor"
    DISPATCHER = "dispatcher"
    BENEFICIARY = "beneficiary"
    GUARDIAN = "guardian"
    RIVAL = "rival"
    FALSE_ALLY = "false_ally"
    CATALYST = "catalyst"
    VICTIM = "victim"
    MENTOR = "mentor"


class PlotSkeleton(BaseModel):
    """One reusable dramatic shape offered to the writer as raw material."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    layers: tuple[Layer, ...] = Field(min_length=1)
    description: str = Field(min_length=1)
    signals: tuple[str, ...] = Field(min_length=1)
    central_tension: str = Field(min_length=1)
    pressure_questions: tuple[str, ...] = Field(min_length=2)
    possible_movements: tuple[str, ...] = Field(min_length=3)
    variants: tuple[str, ...] = Field(default=())
    typical_functional_roles: tuple[FunctionalRole, ...] = Field(default=())
    pairs_well_with: tuple[str, ...] = Field(default=())
    tensions_with: tuple[str, ...] = Field(default=())
    influences: tuple[str, ...] = Field(default=())

    def catalog_entry(self) -> dict[str, object]:
        """Return the compact view sent to the model, hiding thesis-only attribution."""
        return {
            "id": self.id,
            "name": self.name,
            "layers": [layer.value for layer in self.layers],
            "description": self.description,
            "signals": list(self.signals),
            "central_tension": self.central_tension,
        }
