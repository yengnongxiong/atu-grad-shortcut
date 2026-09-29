"""FastAPI application: serves /api and the built frontend from one process."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shortcut.schemas.api import HealthResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Shortcut API", version="0.1.0")

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built SPA (if present) with an index.html fallback for client routes."""
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return
    assets = STATIC_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        candidate = (STATIC_DIR / path).resolve()
        if path and candidate.is_file() and STATIC_DIR in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
