"""Exam credit already on a student's record (Degree Works 'CE' rows), PRD v1.1 §3.3."""

from shortcut.data.loader import load_dataset
from shortcut.planner.profile import build_state, resolve_exam_awards
from shortcut.schemas.plan import CompletedCourse, ExamScore, StudentProfile

CS = "computer-science-2025-26"


def _profile(**kw: object) -> StudentProfile:
    return StudentProfile.model_validate({"program_id": CS, "first_term": "2025FA", **kw})


def test_posted_exam_credit_counts_toward_cap_not_residency() -> None:
    p = _profile(
        completed=[CompletedCourse(code="COMS 1013", grade="P", source="exam", exam="AP Computer Science A")]
    )
    state = build_state(load_dataset(), p, [])
    assert state.exam_hours == 3.0
    assert state.atu_hours == 0.0
    assert state.credits["COMS 1013"].grade is None


def test_audit_hours_override_catalog_hours() -> None:
    p = _profile(completed=[CompletedCourse(code="HIST 2003", grade="A", source="atu", hours=4)])
    assert build_state(load_dataset(), p, []).earned_hours == 4.0


def test_posted_credit_and_score_for_same_course_count_once() -> None:
    ds = load_dataset()
    p = _profile(
        completed=[CompletedCourse(code="ENGL 1013", grade="P", source="exam")],
        exams=[ExamScore(program="CLEP", exam="College Composition", score=52)],
    )
    state = build_state(ds, p, [])
    resolve_exam_awards(state, ds.program(CS), ds)
    assert state.exam_hours == 3.0


def test_plan_accepts_posted_exam_credit() -> None:
    from fastapi.testclient import TestClient

    from shortcut.api.app import create_app

    body = {
        "profile": {
            "program_id": CS,
            "first_term": "2025FA",
            "completed": [{"code": "COMS 1411", "grade": "P", "source": "exam", "hours": 1, "exam": "AP35"}],
        },
        "include_attribution": False,
    }
    res = TestClient(create_app()).post("/api/plan", json=body)
    assert res.status_code == 200
    credited = {c["code"]: c for c in res.json()["credited"]}
    assert credited["COMS 1411"]["hours"] == 1.0
    assert credited["COMS 1411"]["source"] == "exam"
