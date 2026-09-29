"""FastAPI application: serves /api and the built frontend from one process."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from shortcut.api.routes import router

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Shortcut API",
        version="0.1.0",
        description="Fastest realistic path to graduation for ATU students. Not affiliated with ATU.",
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.include_router(router)
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

    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    def spa(path: str) -> FileResponse | JSONResponse:
        if path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = (STATIC_DIR / path).resolve()
        if path and candidate.is_file() and STATIC_DIR in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
