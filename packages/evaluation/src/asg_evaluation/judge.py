"""Interpretable pairwise preference learning without held-out story leakage."""

from __future__ import annotations

import warnings
from collections import defaultdict

import numpy as np
import sklearn
from scipy.special import expit
from scipy.stats import kendalltau
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from .catalog import CRITERIA, catalog_snapshot, core_ids, digest
from .preferences import bradley_terry, decided_votes

MODEL_VERSION = 2


def protocol(identity: dict) -> dict:
    """Return the extraction procedure that must match between training and scoring."""
    return {key: identity.get(key) for key in ("version", "prompt_version", "model")}


def feature_vector(report: dict, fields: list[str]) -> list[float | None]:
    """Read numeric measured features; preserve failed and inapplicable values as missing."""
    values = []
    for key in fields:
        entry = report.get("features", {}).get(key, {})
        value = entry.get("value")
        values.append(
            float(value)
            if entry.get("status") == "measured"
            and isinstance(value, int | float)
            and np.isfinite(value)
            else None
        )
    return values


def fit_linear(vectors: dict[str, list], votes: list[dict], fields: list[str]) -> dict:
    """Fit preprocessing once per unique training story, followed by antisymmetric pairs."""
    stories = sorted({s for v in votes for s in (v["left"], v["right"])})
    if len(stories) < 3 or len(votes) < 2:
        raise ValueError("No hay suficientes historias y comparaciones para entrenar.")
    raw = np.array([vectors[s] for s in stories], dtype=float)
    available = np.isfinite(raw).any(axis=0)
    if not available.any():
        raise ValueError("No hay rasgos medidos para entrenar.")
    medians = np.zeros(len(fields))
    medians[available] = np.nanmedian(raw[:, available], axis=0)
    filled = np.where(np.isfinite(raw), raw, medians)
    means = filled.mean(axis=0)
    scales = filled.std(axis=0)
    scales[scales == 0] = 1
    normalized = (filled - means) / scales
    table = dict(zip(stories, normalized, strict=True))
    differences = np.array([table[v["left"]] - table[v["right"]] for v in votes])
    target = np.array([int(v["choice"] == "A") for v in votes])
    estimator = LogisticRegression(C=1.0, fit_intercept=False, solver="lbfgs", max_iter=2000)
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        estimator.fit(
            np.vstack((differences, -differences)),
            np.r_[target, 1 - target],
            sample_weight=np.full(len(votes) * 2, 0.5),
        )
    weights = estimator.coef_[0]
    scores = normalized @ weights
    return {
        "features": fields,
        "training_stories": stories,
        "medians": medians.tolist(),
        "means": means.tolist(),
        "scales": scales.tolist(),
        "weights": weights.tolist(),
        "inactive_features": [fields[i] for i in range(len(fields)) if not available[i]],
        "score_center": float(scores.mean()),
        "score_scale": float(scores.std()) or 1.0,
    }


def predict(model: dict, vector: list) -> float:
    """Apply frozen preprocessing and coefficients without loading executable model pickles."""
    values = np.array(vector, dtype=float)
    filled = np.where(np.isfinite(values), values, model["medians"])
    return float(((filled - model["means"]) / model["scales"]) @ np.array(model["weights"]))


def _validate(vectors: dict, votes: list[dict], fields: list[str], groups: dict[str, str]) -> dict:
    """Remove every vote touching held-out stories and aggregate out-of-fold probabilities."""
    predictions = defaultdict(list)
    folds = []
    for group in sorted(set(groups.values())):
        held = {s for s, value in groups.items() if value == group}
        train = [v for v in votes if v["left"] not in held and v["right"] not in held]
        test = [(i, v) for i, v in enumerate(votes) if v["left"] in held or v["right"] in held]
        try:
            fitted = fit_linear(vectors, train, fields)
        except (ValueError, ConvergenceWarning):
            folds.append({"held_out": sorted(held), "status": "insufficient"})
            continue
        folds.append(
            {
                "held_out": sorted(held),
                "status": "fitted",
                "train_vote_ids": [v["id"] for v in train],
                "training_stories": fitted["training_stories"],
                "medians": fitted["medians"],
                "means": fitted["means"],
                "scales": fitted["scales"],
            }
        )
        for index, vote in test:
            probability = float(
                expit(
                    predict(fitted, vectors[vote["left"]]) - predict(fitted, vectors[vote["right"]])
                )
            )
            predictions[index].append(probability)
    records = [
        {
            "vote_id": votes[i]["id"],
            "left": votes[i]["left"],
            "right": votes[i]["right"],
            "probability_A": float(np.mean(values)),
            "target_A": votes[i]["choice"] == "A",
        }
        for i, values in sorted(predictions.items())
    ]
    accuracy = [
        0.5
        if abs(r["probability_A"] - 0.5) < 1e-12
        else float((r["probability_A"] > 0.5) == r["target_A"])
        for r in records
    ]
    stories = sorted(vectors)
    predicted_rank = bradley_terry(stories, records, [r["probability_A"] for r in records])
    human_rank = bradley_terry(stories, votes)
    tau = None
    if predicted_rank["status"] == human_rank["status"] == "fitted":
        value = kendalltau(
            [predicted_rank["scores"][s] for s in stories],
            [human_rank["scores"][s] for s in stories],
        ).statistic
        tau = float(value) if np.isfinite(value) else None
    return {
        "accuracy": float(np.mean(accuracy)) if accuracy else None,
        "chance_accuracy": 0.5,
        "tested_votes": len(records),
        "total_votes": len(votes),
        "kendall_tau": tau,
        "predictions": records,
        "folds": folds,
        "predicted_ranking": predicted_rank,
    }


def train_judge(dataset: dict, features: dict[str, dict]) -> dict:
    """Fit three exploratory judges and publish story- and premise-held-out diagnostics."""
    fields = core_ids()
    stories = dataset["stories"]
    for story in stories:
        report = features.get(story["id"], {})
        identity = report.get("identity", {})
        if (
            identity.get("text_hash") != story["text_hash"]
            or identity.get("catalog_hash") != catalog_snapshot()["sha256"]
        ):
            raise ValueError("Los rasgos no corresponden al texto y catálogo congelados.")
        if any(
            report.get("features", {}).get(k, {}).get("status")
            not in {"measured", "not_applicable"}
            for k in fields
        ):
            raise ValueError("Completa la extracción de los 27 rasgos antes de entrenar.")
    protocols = [protocol(features[s["id"]].get("identity", {})) for s in stories]
    if any(p != protocols[0] for p in protocols):
        raise ValueError(
            "Las extracciones usan protocolos distintos (versión, prompt o modelo); "
            "repítelas con uno solo antes de entrenar."
        )
    snapshot = dataset["study"].get("snapshot")
    if not snapshot or snapshot["catalog"]["sha256"] != catalog_snapshot()["sha256"]:
        raise ValueError("El estudio debe estar congelado con este catálogo.")
    vectors = {s["id"]: feature_vector(features[s["id"]], fields) for s in stories}
    families = {s["id"]: s["family"] for s in stories}
    result = {
        "schema_version": MODEL_VERSION,
        "catalog_hash": catalog_snapshot()["sha256"],
        "study_hash": snapshot["sha256"],
        "extraction_protocol": protocols[0] if protocols else None,
        "data_hash": digest({"votes": dataset["votes"], "features": features}),
        "sklearn_version": sklearn.__version__,
        "status": "exploratory",
        "criteria": {},
        "limitations": [
            "Muestra pequeña; no constituye una medida validada de calidad.",
            "Las preferencias pueden depender de premisas y lectores.",
        ],
    }
    for criterion in CRITERIA:
        votes = decided_votes(dataset["votes"], criterion)
        try:
            model = fit_linear(vectors, votes, fields)
        except (ValueError, ConvergenceWarning) as exc:
            result["criteria"][criterion] = {"status": "insufficient", "reason": str(exc)}
            continue
        validation = _validate(vectors, votes, fields, {s: s for s in vectors})
        length = {s: [vector[fields.index("T01")]] for s, vector in vectors.items()}
        length_validation = _validate(length, votes, ["T01"], {s: s for s in vectors})
        result["criteria"][criterion] = {
            "status": "fitted",
            "model": model,
            "validation": validation,
            "length_baseline": length_validation,
            "family_validation": _validate(vectors, votes, fields, families),
        }
    return result


def rank_features(judge: dict, rows: list[dict]) -> dict:
    """Score eligible complete prose using frozen scales and keep three primary rankings."""
    if (
        judge.get("schema_version") != MODEL_VERSION
        or judge.get("catalog_hash") != catalog_snapshot()["sha256"]
    ):
        raise ValueError("Modelo incompatible con el catálogo actual.")
    rankings = {c: [] for c in CRITERIA}
    excluded, combined, scored = [], [], []
    for row in rows:
        reason = _ineligible(row) or (
            "Protocolo de extracción distinto"
            if protocol(row.get("extraction_identity", {})) != judge.get("extraction_protocol")
            else ""
        )
        if reason:
            excluded.append({"story": row["story"], "reason": reason})
            continue
        record = {
            "story": row["story"],
            "generator_version": row.get("generator_version"),
            "pipeline_version": row.get("pipeline_version"),
            "format": row.get("format"),
            "scores": {},
            "missing": [k for k in core_ids() if row["features"][k]["status"] != "measured"],
        }
        standardized = []
        for criterion in CRITERIA:
            entry = judge["criteria"][criterion]
            if entry["status"] != "fitted":
                continue
            model = entry["model"]
            score = predict(model, feature_vector(row, model["features"]))
            record["scores"][criterion] = score
            standardized.append((score - model["score_center"]) / model["score_scale"])
            rankings[criterion].append({"story": row["story"], "score": score})
        if len(standardized) == 3:
            record["combined"] = float(np.mean(standardized))
            combined.append({"story": row["story"], "score": record["combined"]})
        scored.append(record)
    for ranking in [*rankings.values(), combined]:
        ranking.sort(key=lambda r: (-r["score"], r["story"]))
    return {
        "status": "exploratory",
        "rankings": rankings,
        "combined_auxiliary": combined,
        "stories": scored,
        "excluded": excluded,
        "top_ten": [
            {"story": r["story"], "observations": "", "strengths": "", "weaknesses": ""}
            for r in combined[:10]
        ],
    }


def _ineligible(row: dict) -> str:
    """Exclude incompatible formats, failed runs and incomplete extractions explicitly."""
    if row.get("status") != "completed":
        return "Run no completado"
    if row.get("format") not in {"baseline", "narrative", "simulated"}:
        return "Formato fuera del estudio en prosa"
    if not row.get("extraction_compatible"):
        return "Extracción ausente u obsoleta"
    if any(
        row["features"].get(k, {}).get("status") not in {"measured", "not_applicable"}
        for k in core_ids()
    ):
        return "Extracción incompleta"
    return ""


def perturbation_report(judge: dict, cases: list[dict]) -> list[dict]:
    """Compare supplied original/perturbed feature pairs without enforcing a desired outcome."""
    results = []
    for case in cases:
        deltas = {}
        for criterion, fitted in judge["criteria"].items():
            if fitted["status"] != "fitted":
                continue
            model = fitted["model"]
            delta = predict(model, feature_vector(case["perturbed"], model["features"])) - predict(
                model, feature_vector(case["original"], model["features"])
            )
            deltas[criterion] = {"delta": delta, "decreased": delta < 0}
        results.append({"name": case["name"], "criteria": deltas})
    return results
