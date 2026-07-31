"""Contratos de salida de Prompt-crafter."""

from pydantic import BaseModel, Field, model_validator

class PromptAlternative(BaseModel):
    id: str = Field(min_length=1, description="Identificador breve y único")
    name: str = Field(min_length=1, description="Nombre breve del enfoque")
    creative_direction: str = Field(min_length=1)
    prompt: str = Field(min_length=1, description="Prompt autocontenido listo para usar")

class CraftResult(BaseModel):
    original_prompt: str = Field(min_length=1)
    alternatives: list[PromptAlternative] = Field(min_length=3, max_length=3)
    recommended_id: str = Field(min_length=1)
    recommendation_reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_alternatives(self) -> "CraftResult":
        identifiers = [item.id for item in self.alternatives]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Los identificadores de las alternativas deben ser únicos.")
        if self.recommended_id not in identifiers:
            raise ValueError("La recomendación debe referirse a una alternativa existente.")
        return self
