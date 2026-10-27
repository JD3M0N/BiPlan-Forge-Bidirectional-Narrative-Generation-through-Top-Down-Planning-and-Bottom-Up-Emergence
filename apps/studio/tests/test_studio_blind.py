import json

import pytest
from asg_studio import create_app
from fastapi.testclient import TestClient
from studio_fakes import FakeGenerator, settings_loader, simulated_run

WRITE = {"X-StageCraft": "1"}
FIRST = "20260927-100000-el-faro"
SECOND = "20260927-110000-el-faro-compartido"


@pytest.fixture
def setup(tmp_path):
    stories = tmp_path / "Stories"
    simulated_run(stories, FIRST)
    simulated_run(stories, SECOND, memory="shared")
    folder = tmp_path / "Evaluations" / "estudio" / "lecturas"
    folder.mkdir(parents=True)
    pairs = [
        {"x": f"Stagecraft/{FIRST}", "y": f"Stagecraft/{SECOND}"},
        {"x": f"Stagecraft/{SECOND}", "y": f"Stagecraft/{FIRST}"},
    ]
    (folder / "demo.json").write_text(json.dumps({"pares": pairs}), encoding="utf-8")
    return stories, folder


def client_for(stories, folder):
    app = create_app(
        stories_root=stories,
        generator_factory=lambda options: FakeGenerator(stories),
        settings_loader=settings_loader(key=""),
        cache_dir=stories.parent / "cache",
        blind_dir=folder,
    )
    return TestClient(app, base_url="http://127.0.0.1")


def test_a_pair_carries_no_provenance(setup) -> None:
    stories, folder = setup
    with client_for(stories, folder) as client:
        body = client.get("/api/lecturas/demo/pares/1").json()
    text = json.dumps(body, ensure_ascii=False)
    assert set(body) == {"number", "total", "x", "y", "vote"}
    assert set(body["x"]) == {"chapters"}
    assert FIRST not in text and SECOND not in text
    assert "# El faro" not in text
    assert body["x"]["chapters"] and body["total"] == 2


def test_votes_persist_and_the_last_one_wins(setup) -> None:
    stories, folder = setup
    with client_for(stories, folder) as client:
        assert client.get("/api/lecturas").json() == [{"name": "demo", "total": 2, "voted": 0}]
        first = client.put("/api/lecturas/demo/pares/1/voto", json={"winner": "x"}, headers=WRITE)
        assert first.json() == {"voted": 1, "total": 2}
        client.put("/api/lecturas/demo/pares/1/voto", json={"winner": "ninguno"}, headers=WRITE)
        assert client.get("/api/lecturas/demo/pares/1").json()["vote"] == "ninguno"
        assert client.get("/api/lecturas").json()[0]["voted"] == 1
    saved = json.loads((folder / "demo.votos.json").read_text(encoding="utf-8"))
    assert saved["votos"]["1"]["ganador"] == "ninguno"
    assert not list(folder.glob("*.tmp"))


@pytest.mark.parametrize(
    ("method", "url", "body", "headers", "status"),
    [
        ("put", "/api/lecturas/demo/pares/1/voto", {"winner": "x"}, {}, 403),
        ("put", "/api/lecturas/demo/pares/1/voto", {"winner": "z"}, WRITE, 422),
        ("put", "/api/lecturas/demo/pares/3/voto", {"winner": "x"}, WRITE, 404),
        ("get", "/api/lecturas/demo/pares/0", None, {}, 404),
        ("get", "/api/lecturas/otra/pares/1", None, {}, 404),
        ("get", "/api/lecturas/demo.votos/pares/1", None, {}, 404),
    ],
)
def test_bad_requests_are_refused(setup, method, url, body, headers, status) -> None:
    stories, folder = setup
    with client_for(stories, folder) as client:
        response = getattr(client, method)(url, headers=headers, **({"json": body} if body else {}))
    assert response.status_code == status


def test_a_manifest_cannot_reach_outside_the_collections(setup) -> None:
    stories, folder = setup
    pairs = [{"x": "Stagecraft/../../secreto", "y": f"Stagecraft/{FIRST}"}]
    (folder / "malo.json").write_text(json.dumps({"pares": pairs}), encoding="utf-8")
    with client_for(stories, folder) as client:
        assert client.get("/api/lecturas/malo/pares/1").status_code == 404


def test_voting_writes_nothing_under_stories(setup) -> None:
    stories, folder = setup
    before = sorted(path for path in stories.rglob("*"))
    with client_for(stories, folder) as client:
        client.put("/api/lecturas/demo/pares/2/voto", json={"winner": "y"}, headers=WRITE)
    assert sorted(path for path in stories.rglob("*")) == before
