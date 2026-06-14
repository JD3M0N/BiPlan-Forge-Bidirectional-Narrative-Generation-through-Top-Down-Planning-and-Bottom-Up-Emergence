from __future__ import annotations

import time
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import Settings
from app.database import build_engine, init_db
from app.main import create_app
from app.models import Story, StoryAgentRun, User
from app.schemas import StoryGenerateRequest
from app.security import hash_password

from .fakes import FakeGeminiClient, build_story_request


DEFAULT_PASSWORD = "supersecure123"
RUNTIME_DIR = Path(__file__).resolve().parent / ".runtime"
RUNTIME_LOGS_DIR = RUNTIME_DIR / "logs"


def create_database_path() -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / f"test-{uuid4().hex}.db"


def cleanup_sqlite_database(db_path: Path) -> None:
    for suffix in ("", "-shm", "-wal"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()


def create_test_settings(db_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{db_path.resolve().as_posix()}",
        jwt_secret="test-secret-with-at-least-thirty-two-characters",
        frontend_origin="http://localhost:3000",
        log_dir=str((RUNTIME_LOGS_DIR / db_path.stem).resolve()),
    )


def create_test_client(
    db_path: Path,
    *,
    llm_client=None,
    fail_on: str | None = None,
    inconsistent_dependency: bool = False,
    invalid_payload_for: str | None = None,
    blocking_quality_once: bool = False,
    blocking_quality_always: bool = False,
) -> TestClient:
    client = llm_client or FakeGeminiClient(
        fail_on=fail_on,
        inconsistent_dependency=inconsistent_dependency,
        invalid_payload_for=invalid_payload_for,
        blocking_quality_once=blocking_quality_once,
        blocking_quality_always=blocking_quality_always,
    )
    return TestClient(create_app(settings=create_test_settings(db_path), llm_client=client))


def create_test_engine(db_path: Path):
    settings = create_test_settings(db_path)
    engine = build_engine(settings.database_url)
    init_db(engine)
    return engine


def register_user(client: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201
    return response.json()


def login_user(client: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> dict:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()


def wait_for_story_completion(client: TestClient, story_id: str) -> dict:
    for _ in range(30):
        response = client.get(f"/stories/{story_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("Story generation did not finish in time")


def create_user_record(engine, email: str, password: str = DEFAULT_PASSWORD) -> User:
    with Session(engine) as session:
        user = User(email=email, password_hash=hash_password(password))
        session.add(user)
        session.commit()
        session.refresh(user)
        session.expunge(user)
        return user


def create_story_record(engine, user_id: str, payload: dict | None = None) -> Story:
    request = StoryGenerateRequest.parse_obj(payload or build_story_request())
    input_brief = request.to_input_brief()
    story = Story(
        user_id=user_id,
        style=request.style,
        plot=request.plot,
        length=request.length,
        language=request.language,
        pipeline_mode=request.pipeline_mode,
        characters_json=[character.dict() for character in request.characters],
        input_brief=input_brief,
        story_packet={"input_brief": input_brief},
        status="pending",
    )
    with Session(engine) as session:
        session.add(story)
        session.commit()
        session.refresh(story)
        session.expunge(story)
        return story


def get_story(engine, story_id: str) -> Story:
    with Session(engine) as session:
        story = session.get(Story, story_id)
        assert story is not None
        session.expunge(story)
        return story


def list_agent_runs(engine, story_id: str) -> list[StoryAgentRun]:
    with Session(engine) as session:
        runs = session.exec(
            select(StoryAgentRun)
            .where(StoryAgentRun.story_id == story_id)
            .order_by(StoryAgentRun.started_at)
        ).all()
        for run in runs:
            session.expunge(run)
        return runs
