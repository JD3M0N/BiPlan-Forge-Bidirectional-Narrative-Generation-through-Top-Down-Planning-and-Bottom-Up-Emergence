import json
from collections import Counter

import pytest
from asg_stagecraft.planning.profiles import NarrativeProfile
from asg_stagecraft.tools.guidance_experiment import experiment_manifest, main
from test_generator_v5 import make_request


def reviewed_requests(full=False):
    return [
        make_request().model_copy(
            update={"title": f"Case {profile} {index}", "narrative_profile": profile}
        )
        for profile in NarrativeProfile
        for index in range(2 if full else 1)
    ]


@pytest.mark.parametrize(("full", "count"), [(False, 9), (True, 36)])
def test_manifest_balances_arms_and_freezes_the_same_request(full, count):
    result = experiment_manifest(reviewed_requests(full), model="fixed-model", full=full)
    jobs = result["jobs"]
    assert len(jobs) == count and len({row["job_id"] for row in jobs}) == count
    assert Counter(row["arm"] for row in jobs) == {
        "no_guidance": count // 3,
        "hybrid_v1": count // 3,
        "compositional_v2": count // 3,
    }
    for row in jobs:
        peers = [other for other in jobs if other["request_hash"] == row["request_hash"]]
        assert all(other["request"] == row["request"] for other in peers)
        assert row["options"]["narrative_profile"] == row["request"]["narrative_profile"]
    assert not result["budget_estimate"]["authorized"]
    assert result == experiment_manifest(reviewed_requests(full), model="fixed-model", full=full)


def test_preparation_validates_balance_and_uses_pilot_cost_without_generating(tmp_path):
    with pytest.raises(ValueError, match="premisas"):
        experiment_manifest(reviewed_requests()[:2], model="m")
    paths = []
    for index, request in enumerate(reviewed_requests()):
        path = tmp_path / f"request-{index}.json"
        path.write_text(request.model_dump_json(), encoding="utf-8")
        paths.append(str(path))
    usage = tmp_path / "usage.json"
    usage.write_text(json.dumps({"calls": 20, "total_tokens": 100000}), encoding="utf-8")
    output = tmp_path / "manifest.json"
    assert main([*paths, "--model", "m", "--pilot-usage", str(usage), "--output", str(output)]) == 0
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["budget_estimate"]["calls"] == 180
    assert document["budget_estimate"]["total_tokens"] == 900000
    assert document["status"] == "planned_not_generated"
    with pytest.raises(SystemExit) as error:
        main([*paths, "--model", "m", "--output", str(output)])
    assert error.value.code == 2
