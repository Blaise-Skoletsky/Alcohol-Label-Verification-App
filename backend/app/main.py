import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.controllers import (
    batch_router,
    config_router,
    health_router,
    verification_router,
)
from app.core.settings import get_settings

logger = logging.getLogger("alv.api")


def configure_app_logging() -> None:
    alv_logger = logging.getLogger("alv")
    alv_logger.setLevel(logging.INFO)
    uvicorn_handlers = logging.getLogger("uvicorn.error").handlers
    if uvicorn_handlers and not alv_logger.handlers:
        for handler in uvicorn_handlers:
            alv_logger.addHandler(handler)
        alv_logger.propagate = False
    elif not alv_logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        alv_logger.addHandler(handler)
        alv_logger.propagate = True


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_app_logging()
    yield


def create_app() -> FastAPI:
    configure_app_logging()
    settings = get_settings()
    app = FastAPI(title="Alcohol Label Verification App", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_batch_request_start(request: Request, call_next):
        if request.method == "POST" and request.url.path == "/api/batches":
            started = time.perf_counter()
            logger.info(
                "Batch upload request received: content_length=%s content_type=%s",
                request.headers.get("content-length", "unknown"),
                request.headers.get("content-type", "unknown"),
            )
            response = await call_next(request)
            logger.info(
                "Batch upload request completed: status_code=%s duration_ms=%s",
                response.status_code,
                round((time.perf_counter() - started) * 1000),
            )
            return response
        return await call_next(request)

    app.include_router(health_router)
    app.include_router(config_router)
    app.include_router(verification_router)
    app.include_router(batch_router)

    mount_static_frontend(app)
    return app


def mount_static_frontend(app: FastAPI) -> None:
    static_dir = Path(os.environ.get("STATIC_DIR", Path(__file__).resolve().parents[2] / "static"))
    index_path = static_dir / "index.html"
    if not static_dir.exists():
        return

    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        requested = static_dir / full_path
        if requested.is_file():
            return FileResponse(requested)
        return FileResponse(index_path)


app = create_app()
