"""Independent catalog types shared by artifacts and narrative planning."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


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
