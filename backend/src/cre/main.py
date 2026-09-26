"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from cre.api.v1 import routes
from cre.config import Settings, StorageBackend, get_settings
from cre.container import Container, build_container
from cre.errors import CREError
from cre.logging_config import configure_logging, get_logger

log = get_logger(__name__)


def create_app(settings: Settings | None = None, start_worker: bool = True) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.env, settings.debug)
    container: Container = build_container(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await container.startup(start_worker=start_worker)
        try:
            yield
        finally:
            await container.shutdown()

    app = FastAPI(
        title="Creative Reformatting Engine",
        version="0.1.0",
        description=(
            "Subject-aware media reformatting. One master produces every "
            "platform-ready ratio, each validated against a machine-readable "
            "spec sheet before it enters the library."
        ),
        lifespan=lifespan,
    )
    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.dependency_overrides[routes.get_container] = lambda: container
    app.include_router(routes.router, prefix=settings.api_prefix)

    # Locally the data directory is served directly; with S3 the storage adapter
    # hands out presigned URLs instead and this mount is unnecessary.
    if settings.storage_backend is StorageBackend.LOCAL:
        settings.ensure_dirs()
        app.mount("/media", StaticFiles(directory=settings.data_dir), name="media")

    @app.exception_handler(CREError)
    async def _cre_error(_request: Request, exc: CREError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": str(exc)}},
        )

    @app.get("/health", tags=["ops"])
    async def health() -> dict:
        return {
            "status": "ok",
            "env": settings.env,
            "spec": f"{container.spec.spec_id}@{container.spec.spec_version}",
            "profiles": len(container.spec.profiles),
            "backends": {
                "storage": settings.storage_backend.value,
                "queue": settings.queue_backend.value,
                "repository": settings.repository_backend.value,
            },
        }

    return app


app = create_app()
