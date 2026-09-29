"""AP and IB credit in the planner (PRD v1.1 §3.1)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from shortcut.api.app import create_app
from shortcut.data.loader import load_dataset
from shortcut.planner.exams import exam_opportunities
from shortcut.planner.profile import exam_awards
from shortcut.schemas.plan import PlanRequest, StudentProfile

CS = "computer-science-2025-26"


def _profile(**kw: Any) -> StudentProfile:
    return StudentProfile.model_validate({"program_id": CS, "first_term": "2026FA", **kw})


def test_ap_score_awards_its_courses_and_counts_toward_the_exam_cap() -> None:
    body = {
        "profile": {
            "program_id": CS,
            "first_term": "2026FA",
            "exams": [{"program": "AP", "exam": "Computer Science A", "score": 3}],
        },
        "include_attribution": False,
    }
    plan = TestClient(create_app()).post("/api/plan", json=body).json()
    credited = {c["code"]: c for c in plan["credited"]}
    assert {"COMS 1013", "COMS 1011"} <= set(credited)
    assert credited["COMS 1013"]["source"] == "exam"
    assert plan["totals"]["exam_hours"] == 4.0


def test_same_exam_name_in_two_programs_are_different_exams() -> None:
    awards = exam_awards(
        load_dataset(),
        _profile(exams=[{"program": "AP", "exam": "French Language", "score": 3}]),
        ["clep-french-language-50"],
    )
    assert {a.exam_id for a in awards} == {"ap-french-language-3", "clep-french-language-50"}


def test_generic_credit_only_exam_does_not_break_the_plan() -> None:
    body = {
        "profile": {
            "program_id": CS,
            "first_term": "2026FA",
            "exams": [{"program": "AP", "exam": "African American Studies", "score": 4}],
        },
        "include_attribution": False,
    }
    assert TestClient(create_app()).post("/api/plan", json=body).status_code == 200


def test_ap_and_ib_are_offered_only_to_incoming_students() -> None:
    ds = load_dataset()
    incoming = PlanRequest(profile=_profile(math_act=27))
    continuing = PlanRequest(
        profile=_profile(
            first_term="2025FA", plan_from="2026FA", completed=[{"code": "ENGL 1013", "grade": "A"}]
        )
    )
    incoming_programs = {o.program for o in exam_opportunities(ds, incoming).opportunities}
    continuing_programs = {o.program for o in exam_opportunities(ds, continuing).opportunities}
    assert {"AP", "CLEP"} <= incoming_programs
    assert continuing_programs == {"CLEP"}


def test_exams_endpoint_explains_generic_credit() -> None:
    tables = {t["program"]: t for t in TestClient(create_app()).get("/api/exams").json()["tables"]}
    aas = next(r for r in tables["AP"]["equivalencies"] if r["exam"] == "African American Studies")
    assert aas["awards"] == [] and aas["generic_credit"] == "3 hours General Education Humanities"
