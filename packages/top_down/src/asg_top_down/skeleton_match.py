"""Hybrid lexical and semantic ranking of plot skeletons against a story request."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import TYPE_CHECKING

from .errors import NON_DEGRADABLE_ERRORS
from .schemas import (
    SemanticSkeletonRanking,
    SkeletonMatch,
    StoryRequest,
)
from .skeletons import (
    FALLBACK_SHORTLIST,
    PLOT_SKELETONS,
    SKELETONS_BY_ID,
    PlotSkeleton,
)

if TYPE_CHECKING:
    from .provider import LanguageModelProvider

LEXICAL_WEIGHT = 0.70
SEMANTIC_WEIGHT = 0.30

FIELD_WEIGHTS: dict[str, float] = {
    "name": 1.0,
    "signals": 1.0,
    "variants": 0.65,
    "central_tension": 0.45,
    "pressure_questions": 0.35,
    "description": 0.30,
}

_MIN_TOKEN_LENGTH = 3
_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "but",
        "can",
        "cannot",
        "does",
        "for",
        "from",
        "had",
        "has",
        "have",
        "his",
        "her",
        "into",
        "its",
        "must",
        "not",
        "one",
        "only",
        "other",
        "our",
        "out",
        "own",
        "she",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "too",
        "under",
        "very",
        "was",
        "were",
        "what",
        "when",
        "which",
        "while",
        "who",
        "whose",
        "will",
        "with",
        "would",
        "you",
        "your",
    }
)
_PHRASE_BONUS = 1.5
_TOKEN_CREDIT = 0.35
_SQUASH_SCALE = 3.0

_SEMANTIC_INSTRUCTION = (
    "Rate independently how strongly each plot skeleton resonates with the story request. "
    "Return every skeleton id exactly once with a relevance between 0 and 1. The values do not "
    "have to sum to 1. Judge the underlying dramatic shape, not shared vocabulary."
)


def is_scorable(token: str) -> bool:
    """Reject tokens too short or too common to distinguish one skeleton from another."""
    return len(token) >= _MIN_TOKEN_LENGTH and token not in _STOPWORDS


def normalize(value: str) -> str:
    """Fold text to lowercase ASCII words so Spanish accents never block a match."""
    folded = unicodedata.normalize("NFKD", value.casefold())
    ascii_text = folded.encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def skeleton_query(request: StoryRequest) -> str:
    """Build the scored text, led by the one field the analyst reliably writes in English."""
    parts = [
        request.processed_prompt,
        request.title,
        request.genre,
        request.tone,
        request.premise,
        *request.constraints,
        *request.creative_directions,
    ]
    return "\n".join(part for part in parts if part)


def _weighted_fields(item: PlotSkeleton) -> list[tuple[str, float]]:
    """Flatten one skeleton into scored phrases paired with their field weight."""
    fields: list[tuple[str, float]] = []
    for field_name, weight in FIELD_WEIGHTS.items():
        value = getattr(item, field_name)
        values = value if isinstance(value, tuple) else (value,)
        fields.extend((entry, weight) for entry in values)
    return fields


def _document_tokens(item: PlotSkeleton) -> set[str]:
    """Return every scorable token belonging to one skeleton."""
    return {
        token
        for value, _ in _weighted_fields(item)
        for token in normalize(value).split()
        if is_scorable(token)
    }


def _inverse_document_frequency(documents: list[set[str]]) -> dict[str, float]:
    """Weight tokens so words shared by most skeletons carry little evidence."""
    total = len(documents)
    frequencies = {
        token: sum(token in document for document in documents) for token in set().union(*documents)
    }
    return {
        token: 1.0 + math.log((total + 1) / (count + 1)) for token, count in frequencies.items()
    }


def _score_one(
    item: PlotSkeleton,
    prompt_tokens: set[str],
    padded_prompt: str,
    idf: dict[str, float],
) -> tuple[float, set[str]]:
    """Accumulate phrase and token evidence for a single skeleton."""
    raw_score = 0.0
    matched: set[str] = set()
    counted: set[tuple[str, str]] = set()
    for value, weight in _weighted_fields(item):
        phrase = normalize(value)
        if not phrase:
            continue
        phrase_tokens = [token for token in phrase.split() if is_scorable(token)]
        if phrase_tokens and f" {phrase} " in padded_prompt:
            phrase_idf = sum(idf.get(token, 1.0) for token in phrase_tokens) / len(phrase_tokens)
            raw_score += _PHRASE_BONUS * weight * phrase_idf
            matched.add(phrase)
        for token in prompt_tokens.intersection(phrase_tokens):
            evidence = (value, token)
            if evidence in counted:
                continue
            raw_score += _TOKEN_CREDIT * weight * idf.get(token, 1.0)
            counted.add(evidence)
            matched.add(token)
    return raw_score, matched


def lexical_scores(query: str) -> list[SkeletonMatch]:
    """Rank every skeleton by weighted TF-IDF overlap with the query text."""
    normalized_query = normalize(query)
    prompt_tokens = {token for token in normalized_query.split() if is_scorable(token)}
    documents = [_document_tokens(item) for item in PLOT_SKELETONS]
    idf = _inverse_document_frequency(documents)
    padded_prompt = f" {normalized_query} "

    scored: list[SkeletonMatch] = []
    for index, item in enumerate(PLOT_SKELETONS):
        raw_score, matched = _score_one(item, prompt_tokens, padded_prompt, idf)
        bounded = 0.0 if not normalized_query else 1.0 - math.exp(-raw_score / _SQUASH_SCALE)
        bounded = min(1.0, max(0.0, bounded))
        scored.append(
            SkeletonMatch(
                skeleton_id=item.id,
                score=bounded,
                lexical_score=bounded,
                matched_terms=sorted(matched),
                catalog_order=index,
            )
        )
    return scored


def semantic_scores(
    query: str,
    provider: LanguageModelProvider | None,
) -> dict[str, float] | None:
    """Ask the model to rate every skeleton once, returning None when unavailable."""
    if provider is None or not normalize(query):
        return None
    catalog = [item.catalog_entry() for item in PLOT_SKELETONS]
    try:
        ranking = provider.generate_structured(
            system_instruction=_SEMANTIC_INSTRUCTION,
            prompt=f"STORY REQUEST:\n{query}\n\nSKELETON CATALOG:\n{catalog}",
            schema=SemanticSkeletonRanking,
            profile="extraction",
        )
    except NON_DEGRADABLE_ERRORS:
        raise
    except Exception:
        return None
    resolved = {
        entry.skeleton_id: entry.relevance
        for entry in ranking.scores
        if entry.skeleton_id in SKELETONS_BY_ID
    }
    if not resolved:
        return None
    return {item.id: resolved.get(item.id, 0.0) for item in PLOT_SKELETONS}


def _fallback_matches(limit: int) -> list[SkeletonMatch]:
    """Return a deliberately varied shortlist when the query yields no evidence."""
    order = {item.id: index for index, item in enumerate(PLOT_SKELETONS)}
    return [
        SkeletonMatch(
            skeleton_id=skeleton_id,
            score=0.0,
            lexical_score=0.0,
            matched_terms=[],
            catalog_order=order[skeleton_id],
        )
        for skeleton_id in FALLBACK_SHORTLIST[:limit]
    ]


def rank_skeletons(
    query: str,
    *,
    provider: LanguageModelProvider | None = None,
    limit: int = 10,
) -> list[SkeletonMatch]:
    """Blend lexical and semantic evidence into one auditable skeleton ranking."""
    lexical = lexical_scores(query)
    semantic = semantic_scores(query, provider)

    blended: list[SkeletonMatch] = []
    for match in lexical:
        semantic_score = None if semantic is None else semantic[match.skeleton_id]
        if semantic_score is None:
            final = match.lexical_score
        else:
            final = LEXICAL_WEIGHT * match.lexical_score + SEMANTIC_WEIGHT * semantic_score
        blended.append(
            match.model_copy(
                update={
                    "score": min(1.0, max(0.0, final)),
                    "semantic_score": semantic_score,
                }
            )
        )

    ranked = sorted(
        blended,
        key=lambda row: (-row.score, -row.lexical_score, row.catalog_order),
    )
    if not any(row.score > 0 for row in ranked):
        return _fallback_matches(limit)
    return [row for row in ranked if row.score > 0][:limit]
