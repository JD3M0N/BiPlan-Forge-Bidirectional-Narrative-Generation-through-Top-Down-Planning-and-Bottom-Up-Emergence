"""Routes that read stored runs: the library, one run, its performance, audio and comparison."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api")


@router.get("/runs")
def list_runs(request: Request, collection: str | None = None) -> list[dict]:
    """Return the stored runs, newest first, optionally of one collection."""
    return request.app.state.library.list_runs(collection)


@router.get("/runs/{collection}/{run_id}")
def run_detail(collection: str, run_id: str, request: Request) -> dict:
    """Return everything the reader shows about one run."""
    return request.app.state.library.detail(collection, run_id)


@router.get("/runs/{collection}/{run_id}/performance")
def run_performance(
    collection: str, run_id: str, request: Request, voice: str = "", narrator: str = ""
) -> dict:
    """Return the performed log, marking what a point of view could see of it."""
    return request.app.state.library.performance(collection, run_id, voice=voice, narrator=narrator)


@router.get("/runs/{collection}/{run_id}/audio")
def run_audio(collection: str, run_id: str, request: Request) -> FileResponse:
    """Stream the run's narration."""
    return FileResponse(
        request.app.state.library.audio_path(collection, run_id), media_type="audio/mpeg"
    )


@router.get("/runs/{collection}/{run_id}/replay")
def run_replay(collection: str, run_id: str, request: Request) -> dict:
    """Return the Create form that would repeat this run."""
    return request.app.state.library.replay(collection, run_id)


@router.get("/compare")
def compare(request: Request, runs: Annotated[str, Query()] = "") -> dict:
    """Put two to four runs side by side."""
    references = [item for item in runs.split(",") if item]
    if not 2 <= len(references) <= 4:
        raise HTTPException(status_code=422, detail="Elige entre dos y cuatro funciones.")
    return request.app.state.library.compare(references)
