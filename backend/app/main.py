import os
from pathlib import Path

from fastapi import FastAPI
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


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Alcohol Label Verification App")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
