"""Human preference aggregation, agreement and clustered uncertainty."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from .catalog import CRITERIA
from .study_design import components


def decided_votes(votes: list[dict], criterion: str | None = None) -> list[dict]:
    """Remove abstentions without recoding them as a preference or tie."""
    return [
        v
        for v in votes
        if v["choice"] != "abstain" and (criterion is None or v["criterion"] == criterion)
    ]


def bradley_terry(stories: list[str], votes: list[dict], probabilities=None) -> dict:
    """Fit centered ridge-regularized strengths only for a connected comparison graph."""
    graph = components(stories, [(v["left"], v["right"]) for v in votes])
    if len(stories) < 2 or len(graph) != 1 or not votes:
        return {"status": "insufficient", "components": graph, "scores": {}, "ranking": []}
    index = {s: i for i, s in enumerate(stories)}
    design = np.zeros((len(votes), len(stories)))
    for row, vote in enumerate(votes):
        design[row, index[vote["left"]]] = 1
        design[row, index[vote["right"]]] = -1
    target = np.array(
        probabilities if probabilities is not None else [float(v["choice"] == "A") for v in votes]
    )

    def objective(weights):
        """Evaluate stable fractional Bernoulli loss and its analytic gradient."""
        logits = design @ weights
        loss = np.logaddexp(0, logits).sum() - target @ logits + 0.0005 * (weights @ weights)
        gradient = design.T @ (expit(logits) - target) + 0.001 * weights
        return loss, gradient

    fitted = minimize(objective, np.zeros(len(stories)), jac=True, method="L-BFGS-B")
    if not fitted.success:
        return {"status": "failed", "components": graph, "scores": {}, "ranking": []}
    weights = fitted.x - fitted.x.mean()
    scores = dict(zip(stories, weights.tolist(), strict=True))
    return {
        "status": "fitted",
        "components": graph,
        "scores": scores,
        "ranking": sorted(stories, key=lambda s: (-scores[s], s)),
    }


def agreement(votes: list[dict]) -> dict:
    """Compute agreement and nominal alpha on identically oriented repeated pairs."""
    units = defaultdict(dict)
    for vote in votes:
        pair = tuple(sorted((vote["left"], vote["right"])))
        if vote["choice"] != "abstain":
            winner = vote["left"] if vote["choice"] == "A" else vote["right"]
            units[pair][vote["participant"]] = int(winner == pair[0])
    repeated = [list(v.values()) for v in units.values() if len(v) > 1]
    comparisons = [a == b for unit in repeated for a, b in combinations(unit, 2)]
    ratings = [value for unit in repeated for value in unit]
    counts = Counter(ratings)
    total = len(ratings)
    observed = (
        sum(sum(a != b for a in unit for b in unit) / (len(unit) - 1) for unit in repeated) / total
        if total
        else None
    )
    expected = 2 * counts[0] * counts[1] / (total * (total - 1)) if total > 1 else 0
    return {
        "repeated_pairs": len(repeated),
        "reader_pair_comparisons": len(comparisons),
        "agreement": sum(comparisons) / len(comparisons) if comparisons else None,
        "krippendorff_alpha_nominal": 1 - observed / expected if expected else None,
        "abstentions": sum(v["choice"] == "abstain" for v in votes),
    }


def _criterion_report(stories: list[str], votes: list[dict], bootstrap: int, seed: int) -> dict:
    """Resample readers as clusters and disclose disconnected bootstrap replicates."""
    valid = decided_votes(votes)
    result = {**bradley_terry(stories, valid), "agreement": agreement(votes)}
    result["intervals"] = {}
    result["bootstrap"] = {"requested": bootstrap, "valid": 0, "unit": "participant"}
    participants = sorted({v["participant"] for v in valid})
    if result["status"] != "fitted" or len(participants) < 2:
        return result
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(bootstrap):
        selected = rng.choice(participants, len(participants), replace=True)
        draw = [v for p in selected for v in valid if v["participant"] == p]
        fitted = bradley_terry(stories, draw)
        if fitted["status"] == "fitted":
            samples.append([fitted["scores"][s] for s in stories])
    result["bootstrap"]["valid"] = len(samples)
    if samples:
        bounds = np.percentile(samples, [2.5, 97.5], axis=0)
        result["intervals"] = {s: bounds[:, i].tolist() for i, s in enumerate(stories)}
    return result


def human_report(dataset: dict, *, bootstrap: int = 1000, seed: int = 42) -> dict:
    """Report each criterion with and without author participation."""
    if bootstrap < 0:
        raise ValueError("El número de réplicas debe ser no negativo.")
    stories = [s["id"] for s in dataset["stories"]]
    authors = {p["id"] for p in dataset["participants"] if p["is_author"]}
    report = {"interpretation": "Estudio exploratorio; intervalos por lector, no por voto."}
    for label, votes in (
        ("all", dataset["votes"]),
        ("without_author", [v for v in dataset["votes"] if v["participant"] not in authors]),
    ):
        report[label] = {
            c: _criterion_report(
                stories, [v for v in votes if v["criterion"] == c], bootstrap, seed
            )
            for c in CRITERIA
        }
    return report
