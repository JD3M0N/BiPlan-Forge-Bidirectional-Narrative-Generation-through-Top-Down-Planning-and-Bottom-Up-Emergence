"""The one bounded retry loop every rewrite of a drafted unit goes through (7.18, TD-3).

The Writer's chapters and the Script Writer's acts each carried a copy of this loop until 7.17.
It asks for a candidate, has the caller judge it, feeds the rejection back as a correction and,
when no attempt passes, keeps the best one the caller ranked. It knows nothing of chapters, acts
or the repository: the caller binds those in closures, so the loop is tested on its own.

The corrections are reinjected into the model's prompt, so they stay in English.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from ..runtime.errors import NON_DEGRADABLE_ERRORS
from ..schemas import ChapterRevisionAttempt, WriterCandidateDiagnostic

Response = TypeVar("Response")
Candidate = TypeVar("Candidate")


@dataclass
class Judgement(Generic[Candidate]):
    """The caller's verdict on one candidate: why it fails, and how it ranks if it does.

    A rank of None means the candidate may never ship in place of the draft, such as a copy.
    """

    candidate: Candidate
    diagnostic: WriterCandidateDiagnostic | None
    artifact: str | None = None
    rank: tuple[int, ...] | None = None


@dataclass
class LoopOutcome(Generic[Candidate]):
    """What the loop ends with: an accepted candidate, the best rejected one, or neither."""

    accepted: Candidate | None = None
    best: Candidate | None = None
    best_attempt: int | None = None
    attempts: list[ChapterRevisionAttempt] = field(default_factory=list)


def retry_feedback(
    diagnostic: WriterCandidateDiagnostic | None, exception_name: str | None, closing: str
) -> str:
    """Write the correction the next attempt reads after a failed or rejected one."""
    if diagnostic is None:
        return (
            "\n\nRETRY CORRECTION:\nThe previous rewrite could not be completed "
            f"({exception_name}). {closing}"
        )
    return (
        "\n\nRETRY CORRECTION:\nThe previous rewrite was rejected because "
        f"{diagnostic.message}. {diagnostic.retry_instruction} {closing}"
    )


def revise_with_retries(
    attempts: int,
    call: Callable[[int, str], Response],
    judge: Callable[[int, Response], Judgement[Candidate]],
    record: Callable[[ChapterRevisionAttempt], None],
    closing: str,
) -> LoopOutcome[Candidate]:
    """Ask for up to `attempts` candidates and stop at the first one the judge accepts.

    `call(attempt, feedback)` returns the model's response; quota, configuration and
    cancellation errors propagate and any other failure is recorded as a failed attempt.
    `judge(attempt, response)` turns it into a Judgement, saving what it needs to.
    `record(attempt_result)` persists each attempt's outcome. Among rejected
    candidates the lowest rank wins, and the latest one on a tie.
    """
    outcome: LoopOutcome[Candidate] = LoopOutcome()
    best_rank: tuple[int, ...] | None = None
    feedback = ""
    for attempt in range(1, attempts + 1):
        try:
            response = call(attempt, feedback)
        except NON_DEGRADABLE_ERRORS:
            raise
        except Exception as exc:
            result = ChapterRevisionAttempt(
                attempt=attempt, status="failed", exception_type=type(exc).__name__
            )
            outcome.attempts.append(result)
            record(result)
            feedback = retry_feedback(None, type(exc).__name__, closing)
            continue
        judgement = judge(attempt, response)
        result = ChapterRevisionAttempt(
            attempt=attempt,
            status="accepted" if judgement.diagnostic is None else "rejected",
            artifact=judgement.artifact,
            diagnostic=judgement.diagnostic,
        )
        outcome.attempts.append(result)
        record(result)
        if judgement.diagnostic is None:
            outcome.accepted = judgement.candidate
            return outcome
        if judgement.rank is not None and (best_rank is None or judgement.rank <= best_rank):
            best_rank = judgement.rank
            outcome.best = judgement.candidate
            outcome.best_attempt = attempt
        feedback = retry_feedback(judgement.diagnostic, None, closing)
    return outcome
