"""Verified evidence, missingness and resumable measurement."""

import json

import pytest
from asg_evaluation.catalog import core_ids
from asg_evaluation.demo import SyntheticProvider, synthetic_run
from asg_evaluation.feature_audit import compare_extractions
from asg_evaluation.feature_report import read_features
from asg_evaluation.features import (
    FeatureFinding,
    Findings,
    Occurrence,
    Quote,
    Scene,
    Segmentation,
    aggregate_finding,
    extract_features,
    paragraphs,
)


def test_literal_evidence_duplicates_and_empty_denominators():
    text = "Ada tenía la llave.\n\nAda nunca tuvo la llave."
    blocks = paragraphs(text)
    partition = Segmentation(scenes=[Scene(first=0, last=1)])
    occurrence = Occurrence(
        scene=0,
        explanation="Conflicting possession",
        evidence=[
            Quote(paragraph=0, text="Ada tenía la llave."),
            Quote(paragraph=1, text="Ada nunca tuvo la llave."),
        ],
    )
    finding = FeatureFinding(feature="X20", complete=True, occurrences=[occurrence, occurrence])
    value = aggregate_finding(finding, blocks, partition, 10, set())
    assert value["value"] == 1
    for quote in value["evidence"][0]["evidence"]:
        assert text[quote["start"] : quote["end"]] == quote["text"]
    for evidence in ([Quote(paragraph=0, text="inventado")], [occurrence.evidence[0]]):
        wrong = finding.model_copy(
            update={"occurrences": [occurrence.model_copy(update={"evidence": evidence})]}
        )
        with pytest.raises(ValueError):
            aggregate_finding(wrong, blocks, partition, 10, set())
    payoff = FeatureFinding(feature="X24", complete=True)
    assert aggregate_finding(payoff, blocks, partition, 10, set())["status"] == "not_applicable"
    incomplete = payoff.model_copy(update={"complete": False})
    assert aggregate_finding(incomplete, blocks, partition, 10, set())["value"] is None


def test_extraction_resumes_reuses_cache_and_invalidates_changed_text(tmp_path):
    run = synthetic_run(tmp_path / "run", 3)
    text = (run / "story.md").read_text(encoding="utf-8")
    output = run / "features" / "features.json"

    class Interrupted(SyntheticProvider):
        def generate_structured(self, **kwargs):
            if self.calls == 2:
                raise RuntimeError("network unavailable")
            return super().generate_structured(**kwargs)

    with pytest.raises(RuntimeError):
        extract_features(text, Interrupted(), model="fake", output=output)
    checkpoint = json.loads(output.read_text(encoding="utf-8"))
    assert "segmentation" in checkpoint and not checkpoint["complete"]
    provider = SyntheticProvider()
    report = extract_features(text, provider, model="fake", output=output)
    assert provider.calls == 1
    assert report["complete"] and set(core_ids()) <= set(report["features"])
    assert extract_features(text, provider, model="fake", output=output) == report
    assert provider.calls == 1
    table = read_features(run)
    assert table["features"]["P01"]["value"] is None
    assert table["extraction_compatible"]
    (run / "story.md").write_text(text + "\n\nOtra escena.", encoding="utf-8")
    assert not read_features(run)["extraction_compatible"]
    again = extract_features(text, provider, model="fake", output=output, force=True)
    assert all(
        v["equal"] in (True, None) for v in compare_extractions(report, again)["features"].values()
    )


def test_invalid_quotes_get_one_repair_then_remain_failed(tmp_path):
    run = synthetic_run(tmp_path / "run", 1)
    text = (run / "story.md").read_text(encoding="utf-8")

    class Invalid(SyntheticProvider):
        def generate_structured(self, **kwargs):
            clean = {**kwargs, "prompt": kwargs["prompt"].split("\nREPAIR:")[0]}
            response = super().generate_structured(**clean)
            if isinstance(response, Findings):
                response.features[0].occurrences = [
                    Occurrence(
                        scene=0,
                        label="q",
                        explanation="bad",
                        evidence=[Quote(paragraph=1, text="A fabricated quote")],
                    )
                ]
            return response

    output = run / "features" / "features.json"
    provider = Invalid()
    with pytest.raises(ValueError):
        extract_features(text, provider, model="fake", output=output)
    report = json.loads(output.read_text(encoding="utf-8"))
    assert provider.calls == 3
    assert report["features"]["X23"]["status"] == "failed"
    assert report["features"]["X23"]["value"] is None
