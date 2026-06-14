from sqlalchemy import inspect, text
from sqlmodel import SQLModel, Session, create_engine


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args)


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_story_pipeline_mode_column(engine)


def _ensure_story_pipeline_mode_column(engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "story" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("story")}
    if "pipeline_mode" in column_names:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE story ADD COLUMN pipeline_mode VARCHAR DEFAULT 'efficient' NOT NULL")
        )


def get_session(engine):
    return Session(engine)
