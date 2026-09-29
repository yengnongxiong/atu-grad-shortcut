# Shortcut: one service that serves the built React app and the FastAPI /api.
#   docker build -t shortcut .
#   docker run --rm -p 8000:8000 shortcut   ->  http://localhost:8000

# ---- 1. Build the frontend -----------------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# vite.config.ts writes the bundle to ../backend/shortcut/static
RUN npm run build

# ---- 2. Python runtime -----------------------------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
# uv from PyPI (pinned) rather than ghcr.io, so the build also works where only PyPI is reachable.
RUN pip install --no-cache-dir "uv==0.8.*"
WORKDIR /app/backend

# Dependencies first for layer caching.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/shortcut ./shortcut
COPY backend/pipeline ./pipeline
COPY data/processed /app/data/processed
COPY data/personas /app/data/personas
COPY --from=frontend /app/backend/shortcut/static ./shortcut/static
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 shortcut && chown -R shortcut /app
USER shortcut
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["/app/backend/.venv/bin/uvicorn", "shortcut.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
