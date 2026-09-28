"""The StageCraft application: the API the page talks to, and the page itself.

create_app takes everything that touches the outside world as an argument - where the stories
live, how a generator is built, how settings are read - so the tests build the whole app with a
fake generator and a temporary folder, and never call Gemini or write under Stories/.
"""

from __future__ import annotations

import mimetypes
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from asg_stagecraft import StoryGenerator
from asg_stagecraft.runtime.config import load_settings
from asg_stagecraft.runtime.provider import provider_from_settings
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .jobs import GeneratorFactory, JobRunner
from .library import Library, RunNotFound
from .routes import catalog, jobs, runs
from .security import GuardMiddleware

# Windows can map .js to text/plain in its registry, and a browser refuses to run an ES module
# served that way: the page would load blank. Registering the type here fixes every server.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")

STATIC_DIR = Path(__file__).resolve().parent / "static"
LOCAL_HOSTS = ("127.0.0.1", "localhost")

# Pydantic error types, and how the page says them in Spanish.
_ERROR_MESSAGES = {
    "missing": "Falta este dato.",
    "string_too_short": "No puede estar vacío.",
    "too_short": "No puede estar vacío.",
    "string_too_long": "Es demasiado largo.",
    "too_long": "Hay demasiados elementos.",
    "greater_than_equal": "El valor es demasiado pequeño.",
    "less_than_equal": "El valor es demasiado grande.",
    "literal_error": "Ese valor no está entre los permitidos.",
    "enum": "Ese valor no está entre los permitidos.",
    "extra_forbidden": "Ese dato no existe.",
    "int_parsing": "Debe ser un número entero.",
    "bool_parsing": "Debe ser sí o no.",
}


def stagecraft_factory(settings_loader: Callable) -> GeneratorFactory:
    """Build real generators: fresh settings and a fresh provider for every job."""

    def build(options):
        """Read the settings now, so an edit to .env reaches the next job."""
        settings = settings_loader(require_api_key=True)
        provider = provider_from_settings(settings)
        return StoryGenerator.from_options(provider, settings.output_root, options)

    return build


def spanish_errors(error: RequestValidationError) -> list[dict[str, str]]:
    """Turn request validation errors into messages the page can show beside each field."""
    problems = []
    for item in error.errors():
        message = str(item.get("msg", ""))
        if item.get("type") == "value_error":
            message = message.removeprefix("Value error, ")
        else:
            message = _ERROR_MESSAGES.get(str(item.get("type")), message)
        location = [str(part) for part in item.get("loc", ()) if part not in {"body"}]
        problems.append({"field": ".".join(location), "message": message})
    return problems


def create_app(
    *,
    stories_root: Path,
    generator_factory: GeneratorFactory | None = None,
    settings_loader: Callable = load_settings,
    allowed_hosts: tuple[str, ...] = LOCAL_HOSTS,
    demo: bool = False,
    cache_dir: Path | None = None,
) -> FastAPI:
    """Assemble the StageCraft app around its collaborators."""
    runner = JobRunner(generator_factory or stagecraft_factory(settings_loader))

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """Run the job worker for as long as the server lives."""
        runner.start()
        yield
        runner.stop(timeout=5.0)

    application = FastAPI(title="StageCraft", docs_url=None, redoc_url=None, lifespan=lifespan)
    application.state.runner = runner
    application.state.library = Library(stories_root)
    application.state.settings_loader = settings_loader
    application.state.demo = demo
    application.state.cache_dir = cache_dir or (Path(stories_root).parent / ".cache" / "studio")
    application.add_middleware(GuardMiddleware, allowed_hosts=allowed_hosts)

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        """Answer an invalid request with its problems in Spanish, field by field."""
        problems = spanish_errors(error)
        summary = problems[0]["message"] if problems else "La petición no es válida."
        return JSONResponse({"detail": summary, "problems": problems}, status_code=422)

    @application.exception_handler(RunNotFound)
    async def missing_run(request: Request, error: RunNotFound) -> JSONResponse:
        """Answer a request for a run that does not exist."""
        return JSONResponse({"detail": "No existe esa función."}, status_code=404)

    application.include_router(catalog.router)
    application.include_router(jobs.router)
    application.include_router(runs.router)
    application.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return application
