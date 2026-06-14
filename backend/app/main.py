from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.database import build_engine, init_db
from app.logging_utils import configure_logging, get_logger
from app.routers.auth import router as auth_router
from app.routers.stories import router as stories_router
from app.services.gemini import GeminiClient
from app.services.orchestrator import StoryOrchestrator, StoryWorker


def create_app(settings: Settings | None = None, llm_client=None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings)
    logger = get_logger("startup")
    engine = build_engine(app_settings.database_url)
    client = llm_client or GeminiClient(
        api_key=app_settings.gemini_api_key,
        model=app_settings.gemini_model,
        max_retries=app_settings.gemini_max_retries,
        rate_limit_max_retries=app_settings.gemini_rate_limit_max_retries,
        retry_base_seconds=app_settings.gemini_retry_base_seconds,
        min_request_interval_seconds=app_settings.gemini_min_request_interval_seconds,
    )
    orchestrator = StoryOrchestrator(
        engine=engine,
        llm_client=client,
        pipeline_mode=app_settings.gemini_pipeline_mode,
    )
    worker = StoryWorker(orchestrator=orchestrator)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        app.state.settings = app_settings
        app.state.engine = engine
        app.state.worker = worker
        logger.info("Application startup complete")
        await worker.start()
        yield
        logger.info("Application shutdown started")
        await worker.stop()

    app = FastAPI(title=app_settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(stories_router)
    return app


app = create_app()
