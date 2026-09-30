# Shortcut — keep in sync with CLAUDE.md "Commands".
.PHONY: setup pipeline pipeline-offline test test-backend test-frontend lint build serve dev screenshots clean

BACKEND := backend
FRONTEND := frontend
UV := uv --directory $(BACKEND)

setup:
	$(UV) sync
	cd $(FRONTEND) && npm ci

pipeline:
	$(UV) run python -m pipeline.build --online

pipeline-offline:
	$(UV) run python -m pipeline.build --offline

test: test-backend test-frontend

test-backend:
	$(UV) run pytest -q

test-frontend:
	cd $(FRONTEND) && npx vitest run

lint:
	$(UV) run ruff check . ../scripts
	$(UV) run ruff format --check . ../scripts
	$(UV) run mypy
	cd $(FRONTEND) && npx eslint .
	cd $(FRONTEND) && npx tsc -b --noEmit

build:
	cd $(FRONTEND) && npm run build

serve:
	$(UV) run uvicorn shortcut.api.app:app --host 0.0.0.0 --port 8000

dev:
	@echo "Backend on :8000, Vite on :5173 (Ctrl+C stops both)"
	$(UV) run uvicorn shortcut.api.app:app --reload --port 8000 & \
	cd $(FRONTEND) && npx vite --port 5173; \
	kill %1 2>/dev/null || true

# Regenerate docs/screenshots from demo data (run `make build` first).
screenshots:
	$(UV) run playwright install chromium
	$(UV) run python ../scripts/screenshots.py

clean:
	rm -rf $(BACKEND)/shortcut/static $(FRONTEND)/node_modules/.tmp
