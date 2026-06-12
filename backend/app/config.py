from functools import lru_cache

from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Story Writers"
    database_url: str = "sqlite:///./story_writers.db"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 1440
    frontend_origin: str = "http://localhost:3000"
    log_level: str = "INFO"
    log_dir: str = "logs"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_pipeline_mode: str = "efficient"
    gemini_max_retries: int = 3
    gemini_rate_limit_max_retries: int = 8
    gemini_retry_base_seconds: float = 2.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
