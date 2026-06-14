from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=utc_now)


class Story(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    title: str | None = None
    summary: str | None = None
    style: str
    plot: str
    length: str
    language: str = "es"
    pipeline_mode: str = "efficient"
    characters_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    input_brief: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    story_packet: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    story_text: str | None = Field(default=None, sa_column=Column(Text))
    status: str = Field(default="pending", index=True)
    provider: str = "gemini"
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StoryAgentRun(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    story_id: str = Field(foreign_key="story.id", index=True)
    agent_name: str = Field(index=True)
    status: str = Field(default="pending", index=True)
    input_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_snapshot: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
