"""Validate post-performance promise judgements against saved prose and turns."""

from __future__ import annotations

from collections import Counter

from ..schemas import PromiseAuditArtifact, PromiseAuditEntry, PromiseLedger
from .schemas import PerformanceArtifact, PromiseStoryAuditDraft


def materialize_promise_audit(
    draft: PromiseStoryAuditDraft,
    ledger: PromiseLedger,
    performance: PerformanceArtifact,
    story: str,
) -> PromiseAuditArtifact:
    """Count a promise as paid only when its citations really exist."""
    expected = [promise.id for promise in ledger.promises]
    actual = [check.promise_id for check in draft.checks]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError("promise audit must judge each original promise exactly once")
    checks = {item.promise_id: item for item in draft.checks}
    turn_ids = {turn.id for scene in performance.scenes for turn in scene.turns}
    entries = []
    for promise in ledger.promises:
        check = checks[promise.id]
        citation = bool(check.quote.strip() and check.quote.strip() in story)
        supported = bool(check.turn_ids) and set(check.turn_ids) <= turn_ids
        paid = bool(check.paid and citation and supported)
        verdict = "fulfilled" if check.opened and check.progressed and paid else "broken"
        entries.append(
            PromiseAuditEntry(
                promise_id=promise.id,
                kind=promise.kind,
                primary=promise.id == ledger.primary_promise_id,
                verdict=verdict,
                opened=check.opened,
                progressed=check.progressed,
                paid=paid,
                evidence=check.quote if citation else "",
                supporting_turn_ids=check.turn_ids if supported else [],
            )
        )
    return _artifact(entries)


def broken_promise_audit(ledger: PromiseLedger) -> PromiseAuditArtifact:
    """Record an unavailable post-performance judgement as unverified, never fulfilled."""
    return _artifact(
        [
            PromiseAuditEntry(
                promise_id=item.id,
                kind=item.kind,
                primary=item.id == ledger.primary_promise_id,
                verdict="broken",
                opened=False,
                progressed=False,
                paid=False,
                evidence="La actuaci\u00f3n no permiti\u00f3 verificar esta promesa.",
            )
            for item in ledger.promises
        ]
    )


def _artifact(entries: list[PromiseAuditEntry]) -> PromiseAuditArtifact:
    """Summarize validated entries with the same counts as the older audit contract."""
    counts = Counter(item.verdict for item in entries)
    return PromiseAuditArtifact(
        source="performance",
        promises=len(entries),
        fulfilled=counts["fulfilled"],
        weak=counts["weak"],
        broken=counts["broken"],
        fulfilled_ratio=round(counts["fulfilled"] / len(entries), 4) if entries else 0.0,
        entries=entries,
    )
