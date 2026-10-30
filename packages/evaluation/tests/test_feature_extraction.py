"""Verified evidence, missingness and resumable measurement."""

import json

import pytest
from asg_evaluation import features
from asg_evaluation.catalog import catalog, core_ids
from asg_evaluation.feature_audit import compare_extractions
from asg_evaluation.feature_report import read_features
from asg_evaluation.features import (
    FeatureFinding,
    Findings,
    Occurrence,
    Presence,
    Quote,
    Scene,
    Segmentation,
    aggregate_finding,
    dialogue_share,
    extract_features,
    paragraphs,
    scene_features,
)
from evaluation_fakes import SyntheticProvider, synthetic_run


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
    same_quote = [
        Occurrence(scene=0, label=label, explanation="Same passage", evidence=evidence[:1])
        for label, evidence in (("want", occurrence.evidence), ("need", occurrence.evidence))
    ]
    r12 = FeatureFinding(feature="R12", complete=True, occurrences=same_quote)
    assert aggregate_finding(r12, blocks, partition, 10, set())["value"] == 2
    lines = [o.model_copy(update={"label": "Ada"}) for o in same_quote]
    lines.append(same_quote[1].model_copy(update={"label": "Bea"}))
    x08 = aggregate_finding(
        FeatureFinding(feature="X08", complete=True, occurrences=lines),
        blocks,
        partition,
        1000,
        set(),
    )
    assert {k: v["raw"] for k, v in x08["breakdown"].items()} == {"Ada": 1, "Bea": 1}
    cast = Segmentation(
        scenes=[
            Scene(
                first=0, last=0, characters=[Presence(name="Ada", evidence=lines[0].evidence[0])]
            ),
            Scene(first=1, last=1),
        ]
    )
    assert scene_features(cast)["X02"]["breakdown"]["Ada"]["value"] == 0.5
    payoff = FeatureFinding(feature="X24", complete=True)
    assert aggregate_finding(payoff, blocks, partition, 10, set())["status"] == "not_applicable"
    incomplete = payoff.model_copy(update={"complete": False})
    assert aggregate_finding(incomplete, blocks, partition, 10, set())["value"] is None


def test_p04_catalog_changes_count_scenes_payoffs_and_dialogue_share():
    catalog_rows = catalog()
    assert 18 <= len(core_ids()) <= 30 and {"R18", "X29"} <= set(core_ids())
    assert "R12" not in core_ids() and catalog_rows["P35"]["estado"] == "existe"
    text = "Ada habló.\n\nBea calló."
    blocks = paragraphs(text)
    partition = Segmentation(scenes=[Scene(first=0, last=0), Scene(first=1, last=1)])
    change = Occurrence(
        scene=1,
        label="q1",
        explanation="Bea changes",
        evidence=[Quote(paragraph=1, text="Bea calló.")],
    )
    r23 = aggregate_finding(
        FeatureFinding(feature="R23", complete=True, occurrences=[change]),
        blocks,
        partition,
        10,
        set(),
    )
    assert (r23["raw"], r23["denominator"], r23["value"]) == (1, 2, 0.5)
    x24 = aggregate_finding(
        FeatureFinding(feature="X24", complete=True, occurrences=[change]),
        blocks,
        partition,
        10,
        {"q1", "q2"},
    )
    assert x24["value"] == 1 and x24["denominator"] is None
    turns = {"Ada": {"raw": 3}, "Bea": {"raw": 3}}
    even = dialogue_share({"status": "measured", "breakdown": turns})
    skewed = dialogue_share(
        {"status": "measured", "breakdown": {"Ada": {"raw": 5}, "Bea": {"raw": 1}}}
    )
    assert even["value"] == pytest.approx(1.0) and 0 < skewed["value"] < 1
    assert dialogue_share({"status": "measured", "breakdown": {}})["status"] == "not_applicable"
    assert dialogue_share({"status": "failed"})["status"] == "failed"


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
    assert provider.calls == 1  # only the batch after the checkpoint
    assert report["complete"] and set(core_ids()) | {"X08", "X11"} <= set(report["features"])
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


@pytest.fixture
def with_payoffs(monkeypatch):
    """Select X24 as well: it is secondary now, but its dependency on X23 is still code."""
    monkeypatch.setattr(features, "core_ids", lambda: [*core_ids(), "X24"])


@pytest.mark.parametrize("defect", ["fabricated quote", "omitted feature"])
def test_invalid_quotes_get_one_repair_then_remain_failed(tmp_path, defect, with_payoffs):
    run = synthetic_run(tmp_path / "run", 1)
    text = (run / "story.md").read_text(encoding="utf-8")
    prompts = []

    class Invalid(SyntheticProvider):
        def generate_structured(self, **kwargs):
            prompts.append(kwargs["prompt"])
            clean = {**kwargs, "prompt": kwargs["prompt"].split("\nREPAIR:")[0]}
            response = super().generate_structured(**clean)
            if isinstance(response, Findings):
                for finding in [f for f in response.features if f.feature == "X23"]:
                    if defect == "omitted feature":
                        response.features.remove(finding)
                        continue
                    finding.occurrences = [
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
    report = extract_features(text, provider, model="fake", output=output)
    # Segmentation, two batches and one repair that asks only for the invalid field.
    assert provider.calls == 4
    repair = prompts[2].split("FEATURE DEFINITIONS:\n", 1)[1].split("\nREPAIR:")[0]
    assert [d["id"] for d in json.loads(repair)] == ["X23"]
    assert not report["complete"]
    assert report["features"]["X23"]["status"] == "failed"
    assert report["features"]["X23"]["value"] is None
    assert report["features"]["X24"]["status"] == "failed"
    assert report["features"]["R02"]["status"] == "measured"  # valid fields in the batch survive
    retry = SyntheticProvider()
    report = extract_features(text, retry, model="fake", output=output)
    assert retry.calls == 1 and report["complete"]


def test_payoff_is_inapplicable_when_no_question_was_opened(tmp_path, with_payoffs):
    run = synthetic_run(tmp_path / "run", 1)
    text = (run / "story.md").read_text(encoding="utf-8")
    prompts = []

    class NoQuestions(SyntheticProvider):
        def generate_structured(self, **kwargs):
            prompts.append(kwargs["prompt"])
            response = super().generate_structured(**kwargs)
            for finding in getattr(response, "features", []):
                if finding.feature == "X23":
                    finding.applicable, finding.reason = False, "No question is raised"
                    finding.occurrences = []
            return response

    provider = NoQuestions()
    report = extract_features(text, provider, model="fake", output=run / "features.json")
    assert report["complete"] and provider.calls == 3
    assert report["features"]["X24"]["status"] == "not_applicable"
    asked = json.loads(prompts[-1].split("FEATURE DEFINITIONS:\n", 1)[1])
    assert "X24" not in [d["id"] for d in asked]
