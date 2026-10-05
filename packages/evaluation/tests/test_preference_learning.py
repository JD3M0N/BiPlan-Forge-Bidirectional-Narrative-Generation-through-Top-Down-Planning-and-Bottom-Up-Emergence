"""Statistical integrity of preference aggregation and held-out preprocessing."""

from itertools import combinations

import numpy as np
import pytest
from asg_evaluation.judge import _validate, fit_linear, predict
from asg_evaluation.preferences import agreement, bradley_terry, decided_votes


def sample():
    vectors = {str(i): [float(i), None if i == 1 else float(i * 2)] for i in range(6)}
    vectors["5"] = [10000.0, 20000.0]
    votes = [
        {
            "id": str(i),
            "participant": "reader",
            "criterion": "H01",
            "left": a,
            "right": b,
            "choice": "B",
        }
        for i, (a, b) in enumerate(combinations(vectors, 2))
    ]
    return vectors, votes


def test_held_out_stories_and_all_their_votes_are_absent_from_preprocessing():
    vectors, votes = sample()
    result = _validate(vectors, votes, ["T01", "R01"], {s: s for s in vectors})
    assert result["tested_votes"] == len(votes)
    for fold in result["folds"]:
        held = set(fold["held_out"])
        assert held.isdisjoint(fold["training_stories"])
        train = [v for v in votes if v["id"] in fold["train_vote_ids"]]
        assert all(held.isdisjoint((v["left"], v["right"])) for v in train)
        raw = np.array([vectors[s] for s in fold["training_stories"]], dtype=float)
        assert np.allclose(fold["medians"], np.nanmedian(raw, axis=0))
        filled = np.where(np.isfinite(raw), raw, fold["medians"])
        assert np.allclose(fold["means"], filled.mean(axis=0))
    extreme = next(f for f in result["folds"] if f["held_out"] == ["5"])
    assert max(extreme["means"]) < 10


def test_families_are_held_out_together_and_linear_scores_are_antisymmetric():
    vectors, votes = sample()
    groups = {s: str(int(s) // 2) for s in vectors}
    result = _validate(vectors, votes, ["T01", "R01"], groups)
    assert all(len(f["held_out"]) == 2 for f in result["folds"])
    fitted = fit_linear(vectors, votes, ["T01", "R01"])
    assert "intercept" not in fitted
    a, b = predict(fitted, vectors["0"]), predict(fitted, vectors["5"])
    assert a - b == -(b - a)
    with pytest.raises(ValueError):
        fit_linear(vectors, votes[:1], ["T01", "R01"])


def test_abstention_does_not_connect_graph_and_agreement_normalizes_orientation():
    votes = [
        {"left": "a", "right": "b", "choice": "A", "participant": "p1", "criterion": "H01"},
        {"left": "b", "right": "a", "choice": "B", "participant": "p2", "criterion": "H01"},
        {"left": "b", "right": "c", "choice": "abstain", "participant": "p1", "criterion": "H01"},
    ]
    result = bradley_terry(["a", "b", "c"], decided_votes(votes))
    assert result["status"] == "insufficient" and result["ranking"] == []
    result = agreement(votes)
    assert result["agreement"] == 1.0
