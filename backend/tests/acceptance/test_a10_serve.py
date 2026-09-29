"""A10: the frontend builds, one process serves app + API, and every persona renders a plan.

The frontend bundle is produced by `make build` (CI's serve job). Without it the app-serving
assertions are skipped locally unless SHORTCUT_REQUIRE_FRONTEND=1 is set.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from shortcut.api.app import STATIC_DIR, create_app
from shortcut.data.loader import load_dataset


def test_a10_one_process_serves_app_and_api() -> None:
    if not (STATIC_DIR / "index.html").exists():
        if os.environ.get("SHORTCUT_REQUIRE_FRONTEND") == "1":
            pytest.fail("frontend bundle missing: run `make build` first")
        pytest.skip("frontend not built (run `make build`)")
    client = TestClient(create_app())
    home = client.get("/")
    assert home.status_code == 200 and '<div id="root">' in home.text
    deep_link = client.get("/plan?s=abc")
    assert deep_link.status_code == 200 and '<div id="root">' in deep_link.text
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/nope").status_code == 404


def test_a10_every_persona_loads_and_renders_a_plan() -> None:
    client = TestClient(create_app())
    personas = client.get("/api/personas").json()["personas"]
    dataset = load_dataset()
    assert len(personas) == len(dataset.personas) >= 2
    for persona in personas:
        response = client.post("/api/plan", json=persona["request"])
        assert response.status_code == 200, persona["id"]
        plan = response.json()
        assert plan["terms"] or not plan["feasible"], persona["id"]
        assert plan["graduation"] is not None or plan["infeasible_reason"], persona["id"]
