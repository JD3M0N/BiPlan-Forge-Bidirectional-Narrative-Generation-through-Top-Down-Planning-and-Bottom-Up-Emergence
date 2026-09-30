"""One memory stream per character, and the deterministic retrieval that reads it.

The design follows the generative-agents line - recency, importance and relevance combined into
one score - with two departures that matter for this thesis.

First, nothing is embedded: retrieval is lexical, so the same run scores identically on any
machine, with no model call and no vector store. `normalize` is reused from the skeleton matcher,
which already folds Spanish accents away.

Second, and more important, a stream only ever contains what its character perceived. There is
no shared store to leak from: a fact a character never witnessed is not filtered out at read
time, it was never written. That is what keeps a secret a secret without asking a model to keep
one, and it is the difference the `own` / `shared` ablation measures.

Relationship stances are consolidated in CharacterState rather than appended here, so an actor
never reads that it is both allied with and betrayed by the same person.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable

from ..planning.skeleton_match import normalize
from .schemas import MemoryRecord, MemoryRetrieval

# Retrieval weights. Relevance leads because a scene asks about something specific; recency and
# importance break its ties. Company is a small nudge towards memories involving the people
# currently on stage, which is what makes a character bring up a shared past at the right moment.
RELEVANCE_WEIGHT = 1.0
RECENCY_WEIGHT = 0.6
IMPORTANCE_WEIGHT = 0.5
COMPANY_WEIGHT = 0.3

# How fast a memory fades per scene of distance. 0.25 matches the inter-scene penalty that the
# interactive-drama toolkits settled on: distant scenes lose their grip without disappearing.
RECENCY_DECAY = 0.25

# How many long-term records reach a prompt. Small on purpose: a long recall list reads as a
# briefing rather than a memory, and the working memory of the current scene is already complete.
RETRIEVED_RECORDS = 6

# Reflections are how a character carries a scene forward, so the last two always travel,
# whatever they score.
RECENT_REFLECTIONS = 2

# What a character did and thought itself is never recalled verbatim. Its reflections already
# carry those scenes forward in the first person, and an actor that rereads its own old line
# repeats it: the 7.1 runs had one say a whole turn again, word for word, a scene later.
NOT_RECALLED = frozenset({"own_turn", "thought"})

_MIN_TOKEN_LENGTH = 3
# Spanish joins the English set the skeleton catalog already carries: the performance runs in the
# fiction language, so both show up in the same stream.
_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "but",
        "for",
        "from",
        "has",
        "have",
        "her",
        "his",
        "its",
        "not",
        "the",
        "that",
        "them",
        "they",
        "this",
        "was",
        "were",
        "what",
        "when",
        "which",
        "who",
        "will",
        "with",
        "you",
        "your",
        "algo",
        "algun",
        "alguna",
        "alguno",
        "ante",
        "antes",
        "aqui",
        "asi",
        "aun",
        "cada",
        "como",
        "con",
        "contra",
        "cual",
        "cuando",
        "desde",
        "donde",
        "dos",
        "ella",
        "ellas",
        "ello",
        "ellos",
        "entre",
        "era",
        "eran",
        "eres",
        "esa",
        "ese",
        "eso",
        "esta",
        "estan",
        "este",
        "esto",
        "estos",
        "hace",
        "hasta",
        "les",
        "mas",
        "muy",
        "nada",
        "nos",
        "otra",
        "otro",
        "para",
        "pero",
        "poco",
        "por",
        "porque",
        "que",
        "quien",
        "sea",
        "ser",
        "sin",
        "sobre",
        "solo",
        "son",
        "soy",
        "sus",
        "tan",
        "tiene",
        "todo",
        "todos",
        "una",
        "uno",
        "unos",
        "ver",
        "yo",
    }
)


def tokens(text: str) -> list[str]:
    """Split text into the scorable, accent-folded tokens retrieval compares."""
    return [
        token
        for token in normalize(text).split()
        if len(token) >= _MIN_TOKEN_LENGTH and token not in _STOPWORDS
    ]


class CharacterMemory:
    """Everything one character has perceived, and the only view an actor prompt ever gets."""

    def __init__(self, character_id: str) -> None:
        """Start an empty stream for one character."""
        self.character_id = character_id
        self.records: list[MemoryRecord] = []
        self.retrievals: list[MemoryRetrieval] = []
        self._counter = 0
        self.on_record: Callable[[MemoryRecord], None] | None = None
        self._document_frequency: Counter[str] = Counter()

    def remember(
        self,
        *,
        kind: str,
        text: str,
        scene_number: int,
        turn_id: str = "",
        participants: list[str] | None = None,
        importance: float = 0.5,
    ) -> MemoryRecord:
        """Append one record to this character's stream and index it for retrieval."""
        self._counter += 1
        record = MemoryRecord(
            id=f"{self.character_id}-m{self._counter:04d}",
            character_id=self.character_id,
            kind=kind,  # type: ignore[arg-type]
            scene_number=scene_number,
            turn_id=turn_id,
            text=text,
            participants=list(participants or []),
            importance=max(0.0, min(1.0, importance)),
        )
        self.records.append(record)
        if self.on_record:
            self.on_record(record)
        for token in set(tokens(record.text)):
            self._document_frequency[token] += 1
        return record

    def recall(
        self,
        query: str,
        *,
        scene_number: int,
        turn_number: int,
        present: list[str],
        limit: int = RETRIEVED_RECORDS,
    ) -> list[MemoryRecord]:
        """Return this character's most relevant memories of earlier scenes, best first.

        The current scene is excluded on purpose: it already travels whole as working memory,
        and letting it compete here would crowd out everything a character knew beforehand.
        At most ``limit`` records are chosen by score, on top of the last reflections that
        always travel; the character's own lines and thoughts never compete (NOT_RECALLED).
        """
        candidates = [
            record
            for record in self.records
            if record.scene_number < scene_number and record.kind not in NOT_RECALLED
        ]
        if not candidates:
            return []
        scored = [
            (self._score(record, query, scene_number, present), record) for record in candidates
        ]
        scored.sort(key=lambda pair: (-pair[0][0], pair[1].id))

        chosen: list[MemoryRecord] = []
        seen: set[str] = set()
        for record in reversed(candidates):
            if record.kind == "reflection" and len(seen) < RECENT_REFLECTIONS:
                chosen.append(record)
                seen.add(record.id)
        picked = 0
        for breakdown, record in scored:
            if picked >= limit:
                break
            if record.id in seen:
                continue
            chosen.append(record)
            seen.add(record.id)
            picked += 1
            self.retrievals.append(
                MemoryRetrieval(
                    character_id=self.character_id,
                    scene_number=scene_number,
                    turn_number=turn_number,
                    query=query[:200],
                    record_id=record.id,
                    score=round(breakdown[0], 4),
                    recency=round(breakdown[1], 4),
                    importance=round(breakdown[2], 4),
                    relevance=round(breakdown[3], 4),
                    company=round(breakdown[4], 4),
                )
            )
        chosen.sort(key=lambda record: (record.scene_number, record.id))
        return chosen

    def _score(
        self,
        record: MemoryRecord,
        query: str,
        scene_number: int,
        present: list[str],
    ) -> tuple[float, float, float, float, float]:
        """Score one record, returning the total and every term that produced it."""
        recency = 1.0 / (1.0 + RECENCY_DECAY * max(0, scene_number - record.scene_number))
        relevance = self._relevance(record, query)
        company = len(set(record.participants) & set(present)) / len(present) if present else 0.0
        total = (
            RELEVANCE_WEIGHT * relevance
            + RECENCY_WEIGHT * recency
            + IMPORTANCE_WEIGHT * record.importance
            + COMPANY_WEIGHT * company
        )
        return total, recency, record.importance, relevance, company

    def _relevance(self, record: MemoryRecord, query: str) -> float:
        """Score lexical overlap, weighting a term by how rare it is in this character's past."""
        query_tokens = set(tokens(query))
        if not query_tokens:
            return 0.0
        record_tokens = set(tokens(record.text))
        shared = query_tokens & record_tokens
        if not shared:
            return 0.0
        total = max(1, len(self.records))
        weight = sum(
            math.log(1.0 + total / (1 + self._document_frequency[token])) for token in shared
        )
        ceiling = sum(math.log(1.0 + total) for _ in query_tokens) or 1.0
        return min(1.0, weight / ceiling)
