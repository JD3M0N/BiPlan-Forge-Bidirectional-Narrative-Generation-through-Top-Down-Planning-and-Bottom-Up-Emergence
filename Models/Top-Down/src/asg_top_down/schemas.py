"""Contratos de datos entre agentes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StoryRequest(BaseModel):
    original_prompt: str
    title: str = Field(description="Título breve propuesto para la historia")
    language: str = "español"
    genre: str
    tone: str
    target_words: int = Field(default=1500, ge=300, le=20_000)
    premise: str
    constraints: list[str] = Field(default_factory=list)


class WorldArtifact(BaseModel):
    setting: str
    time_period: str
    rules: list[str]
    locations: list[str]
    atmosphere: str


class Character(BaseModel):
    name: str
    role: str
    goal: str
    motivation: str
    conflict: str
    arc: str


class CharactersArtifact(BaseModel):
    characters: list[Character] = Field(min_length=1)
    relationships: list[str] = Field(default_factory=list)


class PlotBeat(BaseModel):
    order: int = Field(ge=1)
    name: str
    purpose: str
    events: list[str]
    characters: list[str]


class OutlineArtifact(BaseModel):
    logline: str
    central_conflict: str
    theme: str
    beats: list[PlotBeat] = Field(min_length=3)
    ending: str


class ReviewArtifact(BaseModel):
    coherence_score: int = Field(ge=1, le=10)
    continuity_score: int = Field(ge=1, le=10)
    style_score: int = Field(ge=1, le=10)
    compliance_score: int = Field(ge=1, le=10)
    strengths: list[str]
    issues: list[str]
    revision_instructions: list[str]


class RunMetadata(BaseModel):
    run_id: str
    model: str
    created_at: datetime
    updated_at: datetime
    status: Literal["running", "completed", "failed"]
    completed_stages: list[str] = Field(default_factory=list)
    error: str | None = None

