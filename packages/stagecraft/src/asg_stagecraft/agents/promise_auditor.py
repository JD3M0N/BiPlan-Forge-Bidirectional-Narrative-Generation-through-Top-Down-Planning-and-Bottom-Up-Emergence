"""Judge whether a performed and narrated story pays its original promises."""

from __future__ import annotations

import json

from ..schemas import PromiseLedger
from ..stage.schemas import PromiseStoryAuditDraft
from .base import Agent


class PromiseStoryAuditorAgent(Agent[PromiseStoryAuditDraft]):
    """Cite exact prose and performed turns for each original promise."""

    name = "promise_auditor"

    def run(self, ledger: PromiseLedger, story: str, turns: list[dict]) -> PromiseStoryAuditDraft:
        """Return a post-performance reading rather than the script critic's prediction."""
        return self.provider.generate_structured(
            system_instruction=(
                "Audit the original promises against the finished story and its performed "
                "turns. Return exactly one check per promise ID. Cite an exact contiguous quote "
                "from the story and the IDs of turns that support it. A promise not actually "
                "paid in the story is unpaid even if the script planned it. An open ending "
                "remains open. Never infer an event from the ledger alone."
            ),
            prompt=(
                f"LEDGER:\n{json.dumps(ledger.model_dump(mode='json'), ensure_ascii=False)}"
                f"\n\nPERFORMED TURNS:\n{json.dumps(turns, ensure_ascii=False)}"
                f"\n\nSTORY:\n{story}"
            ),
            schema=PromiseStoryAuditDraft,
            profile="review",
        )
