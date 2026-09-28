import time

import pytest
from asg_studio import create_app
from fastapi.testclient import TestClient
from studio_fakes import FakeGenerator, settings_loader, simulated_run

WRITE = {"X-StageCraft": "1"}


@pytest.fixture
def stories(tmp_path):
    root = tmp_path / "Stories"
    simulated_run(root, "20260927-100000-el-faro")
    simulated_run(root, "20260927-110000-el-faro-compartido", memory="shared")
    return root


def client_for(stories, *, key="", generator=None):
    app = create_app(
        stories_root=stories,
        generator_factory=lambda options: generator or FakeGenerator(stories),
        settings_loader=settings_loader(key=key),
        cache_dir=stories.parent / "cache",
    )
    return TestClient(app, base_url="http://127.0.0.1")


def test_health_answers_without_a_key(stories) -> None:
    with client_for(stories) as client:
        health = client.get("/api/health").json()
    assert health["name"] == "StageCraft"
    assert health["key_present"] is False
    assert health["demo"] is False


def test_the_catalog_opens_on_the_simulated_format_with_settings_defaults(stories) -> None:
    with client_for(stories, key="secret") as client:
        catalog = client.get("/api/catalog").json()
    assert catalog["defaults"]["story_format"] == "simulated"
    assert catalog["defaults"]["turns_per_beat"] == 6


def test_a_write_without_the_header_is_refused(stories) -> None:
    body = {"mode": "prompt", "prompt": "Una historia"}
    with client_for(stories) as client:
        assert client.post("/api/preview", json=body).status_code == 403
        assert client.post("/api/preview", json=body, headers=WRITE).status_code == 200


def test_a_foreign_host_is_refused(stories) -> None:
    app = create_app(stories_root=stories, settings_loader=settings_loader())
    with TestClient(app, base_url="http://evil.example") as client:
        assert client.get("/api/health").status_code == 400


def test_every_response_carries_a_strict_content_policy(stories) -> None:
    with client_for(stories) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_an_invalid_request_is_explained_in_spanish(stories) -> None:
    body = {
        "mode": "brief",
        "brief": {"plot": "Una trama."},
        "options": {"narrative_voice": "omniscient", "narrator": "Ana"},
    }
    with client_for(stories) as client:
        response = client.post("/api/preview", json=body, headers=WRITE)
    assert response.status_code == 422
    assert "personaje" in response.json()["detail"]


def test_the_preview_shows_the_prompt_and_the_equivalent_command(stories) -> None:
    body = {
        "mode": "brief",
        "brief": {"plot": "Una trama.", "cast": [{"name": "Ana", "role": "protagonista"}]},
        "options": {
            "story_format": "simulated",
            "narrative_voice": "first_person",
            "narrator": "Ana",
            "narration_tone": "como un samurai",
            "promise_ledger": False,
        },
    }
    with client_for(stories) as client:
        preview = client.post("/api/preview", json=body, headers=WRITE).json()
    assert "Reparto (usa exactamente estos nombres" in preview["prompt"]
    assert preview["command"].startswith("$env:ASG_PROMISE_LEDGER='false'; generate-story --brief")
    assert "--voice first_person" in preview["command"]
    assert "--narrator Ana" in preview["command"]
    assert "--tone 'como un samurai'" in preview["command"]


def test_a_job_is_queued_followed_and_finished(stories) -> None:
    body = {"mode": "prompt", "prompt": "Una historia", "options": {"story_format": "narrative"}}
    with client_for(stories) as client:
        job = client.post("/api/jobs", json=body, headers=WRITE)
        assert job.status_code == 201
        job_id = job.json()["id"]
        for _ in range(100):
            snapshot = client.get(f"/api/jobs/{job_id}").json()
            if snapshot["status"] == "completed":
                break
            time.sleep(0.02)
        assert snapshot["status"] == "completed"
        assert client.get("/api/jobs").json()[0]["id"] == job_id
        assert client.get("/api/jobs/nope").status_code == 404


def test_the_library_lists_opens_and_compares_runs(stories) -> None:
    with client_for(stories) as client:
        runs = client.get("/api/runs").json()
        assert [run["actor_memory"] for run in runs] == ["shared", "own"]
        detail = client.get("/api/runs/Stagecraft/20260927-100000-el-faro").json()
        assert detail["story"]["title"] == "El faro"
        assert detail["story"]["chapters"][0]["paragraphs"][0] == "Ana subió."
        comparison = client.get(
            "/api/compare",
            params={
                "runs": "Stagecraft/20260927-100000-el-faro,"
                "Stagecraft/20260927-110000-el-faro-compartido"
            },
        ).json()
        assert comparison["differing_axes"] == ["actor_memory"]
        assert comparison["clean"] is True
        assert client.get("/api/compare", params={"runs": "Stagecraft/x"}).status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/runs/Stagecraft/%2E%2E",
        "/api/runs/Otra/20260927-100000-el-faro",
        "/api/runs/Stagecraft/no-existe",
        "/api/runs/Stagecraft/..%5C..%5Cetc",
    ],
)
def test_a_run_outside_the_collections_cannot_be_reached(stories, path) -> None:
    with client_for(stories) as client:
        assert client.get(path).status_code == 404


def test_the_performance_marks_what_a_voice_cannot_see(stories) -> None:
    with client_for(stories) as client:
        everything = client.get("/api/runs/Stagecraft/20260927-100000-el-faro/performance").json()
        assert all(turn["visible"] for turn in everything["scenes"][0]["turns"])
        limited = client.get(
            "/api/runs/Stagecraft/20260927-100000-el-faro/performance",
            params={"voice": "limited", "narrator": "Ana"},
        ).json()
    turns = limited["scenes"][0]["turns"]
    assert limited["narrator"] == "ana"
    # Ana sees her own turn and her own thought, and not Luis's whisper to nobody but himself.
    assert [turn["visible"] for turn in turns] == [True, False]
    assert turns[0]["thought_visible"] is True


def test_a_run_can_be_replayed_into_the_form(stories) -> None:
    with client_for(stories) as client:
        replay = client.get("/api/runs/Stagecraft/20260927-110000-el-faro-compartido/replay").json()
    assert replay["mode"] == "prompt"
    assert replay["prompt"] == "Una obra"
    assert replay["options"]["actor_memory"] == "shared"


def test_an_unknown_voice_sample_is_not_found(stories) -> None:
    with client_for(stories) as client:
        assert client.get("/api/voices/es-XX-NadieNeural/sample").status_code == 404
