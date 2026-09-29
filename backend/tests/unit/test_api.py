"""API endpoint tests (PRD §11) against the processed dataset."""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any

from fastapi.testclient import TestClient

from shortcut.api.app import create_app

CS = "computer-science-2025-26"


@lru_cache(maxsize=1)
def client() -> TestClient:
    return TestClient(create_app())


def p1_body(**levers: Any) -> dict[str, Any]:
    return {
        "profile": {
            "program_id": CS,
            "first_term": "2026FA",
            "math_act": 27,
            "preferences": {"expect_high_gpa": True},
        },
        "levers": levers,
    }


def test_meta_lists_sources_policies_and_disclaimer() -> None:
    body = client().get("/api/meta").json()
    assert body["newest_catalog_year"] == "2026-27"
    assert body["bachelor_programs"] > 0
    assert any(
        p["key"] == "exam_credit_cap_hours" and p["confidence"] == "conflicting" for p in body["policies"]
    )
    assert all(p["sources"] for p in body["policies"])
    assert "Not affiliated with Arkansas Tech University" in body["disclaimer"]


def test_programs_list_and_detail() -> None:
    programs = client().get("/api/programs").json()
    ids = {p["id"] for p in programs}
    assert CS in ids
    assert all(p["trust_tier"] in ("cross_checked", "auto_imported", "needs_review") for p in programs)
    detail = client().get(f"/api/programs/{CS}").json()
    assert detail["total_hours_min"] == 120
    assert any(r["label"] == "Social Sciences" for r in detail["requirements"])
    assert detail["courses"]["COMS 3213"]["offered"] == "F"
    assert client().get("/api/programs/nope").status_code == 404


def test_exams_endpoint_has_clep_ap_and_ib_from_the_catalog() -> None:
    body = client().get("/api/exams").json()
    tables = {t["program"]: t for t in body["tables"]}
    for program in ("CLEP", "AP", "IB"):
        assert tables[program]["status"] == "available" and tables[program]["equivalencies"]
        assert tables[program]["source"]["url"].startswith("https://catalog.atu.edu/")


def test_personas_endpoint() -> None:
    personas = client().get("/api/personas").json()["personas"]
    assert {"p1", "p2"} <= {p["id"] for p in personas}


def test_plan_endpoint_and_latency() -> None:
    started = time.perf_counter()
    response = client().post("/api/plan", json=p1_body(summer=True, winter=True, heavier_terms=True))
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    body = response.json()
    assert body["feasible"] and body["graduation"]["id"]
    assert body["levers"] and body["terms"]
    assert elapsed < 10  # generous CI bound; p95 is measured separately (PROGRESS.md)


def test_plan_rejects_bad_input() -> None:
    bad = p1_body()
    bad["profile"]["first_term"] = "Fall 26"
    assert client().post("/api/plan", json=bad).status_code == 422
    unknown = p1_body()
    unknown["profile"]["program_id"] = "nope"
    assert client().post("/api/plan", json=unknown).status_code == 404


def test_whatif_endpoint() -> None:
    body = {"plan": p1_body(), "event": {"type": "fail", "code": "COMS 2213"}}
    response = client().post("/api/plan/whatif", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["before"] and data["after"] and data["explanation"]
    missing = {"plan": p1_body(), "event": {"type": "fail", "code": "ZZZ 9999"}}
    assert client().post("/api/plan/whatif", json=missing).status_code == 422


def test_exam_opportunities_endpoint() -> None:
    response = client().post("/api/plan/exam-opportunities", json=p1_body())
    assert response.status_code == 200
    data = response.json()
    assert data["exam_cap_hours"] == 30
    assert data["opportunities"]


def test_delay_impact_endpoint() -> None:
    body = {"plan": p1_body(), "item_id": "COMS 4913"}
    response = client().post("/api/plan/delay-impact", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["explanation"] and data["before"]
