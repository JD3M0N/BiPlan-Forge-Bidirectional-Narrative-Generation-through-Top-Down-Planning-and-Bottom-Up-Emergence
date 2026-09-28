"""Routes that start, follow and stop generations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from ..jobs import JobRequest

router = APIRouter(prefix="/api/jobs")


@router.post("", status_code=201)
def submit(job: JobRequest, request: Request) -> dict:
    """Queue one generation."""
    return request.app.state.runner.submit(job)


@router.get("")
def list_jobs(request: Request) -> list[dict]:
    """Return every job of this session, newest first."""
    return request.app.state.runner.jobs()


@router.get("/{job_id}")
def follow(job_id: str, request: Request, since: Annotated[int, Query(ge=0)] = 0) -> dict:
    """Return one job with the events after the last one the page has seen."""
    snapshot = request.app.state.runner.snapshot(job_id, since)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No existe ese trabajo.")
    return snapshot


@router.post("/{job_id}/cancel")
def cancel(job_id: str, request: Request) -> dict:
    """Withdraw a queued job, or stop a running one at its next agent call."""
    snapshot = request.app.state.runner.cancel(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No existe ese trabajo.")
    return snapshot
