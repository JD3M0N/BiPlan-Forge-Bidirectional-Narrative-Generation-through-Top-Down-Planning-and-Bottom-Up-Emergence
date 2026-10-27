"""Routes of the blind reading view: the sessions, one pair at a time, and the votes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

router = APIRouter(prefix="/api")


class VoteBody(BaseModel):
    """The reader's choice for one pair: X, Y or no difference."""

    model_config = ConfigDict(extra="forbid")

    winner: Literal["x", "y", "ninguno"]


@router.get("/lecturas")
def list_sessions(request: Request) -> list[dict]:
    """Return the reading sessions with their progress."""
    return request.app.state.blind.sessions()


@router.get("/lecturas/{name}/pares/{number}")
def read_pair(name: str, number: int, request: Request) -> dict:
    """Return one pair of stories, anonymized as X and Y."""
    return request.app.state.blind.pair(name, number)


@router.put("/lecturas/{name}/pares/{number}/voto")
def vote(name: str, number: int, body: VoteBody, request: Request) -> dict:
    """Save the reader's choice for one pair."""
    return request.app.state.blind.vote(name, number, body.winner)
