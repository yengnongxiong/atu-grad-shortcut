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


def test_exam_cap_counts_only_courses_the_exam_would_actually_add() -> None:
    """ATU grants no duplicate credit, so a course already held adds no exam-credit hours."""
    from shortcut.planner.exams import exam_opportunities
    from shortcut.schemas.plan import PlanRequest

    ds = load_dataset()
    cap = float(ds.policies.exam_credit_cap_hours)
    # other posted exam credit (outside the program) that brings the total to 3 hours under the cap
    filler, left, n = [], cap - 6, 0
    while left > 0:
        filler.append({"code": f"XEXM {1000 + n}", "grade": "P", "source": "exam", "hours": min(12, left)})
        left, n = left - min(12, left), n + 1
    request = PlanRequest.model_validate(
        {
            "profile": {
                "program_id": CS,
                "first_term": "2025FA",
                "completed": [{"code": "ENGL 1013", "grade": "P", "source": "exam"}, *filler],
            }
        }
    )
    rows = {r.id: r for r in exam_opportunities(ds, request).opportunities}
    comp = next(r for r in rows.values() if r.exam == "College Composition" and r.min_score >= 59)
    assert comp.hours_saved == 3.0  # only ENGL 1023 is new
    assert not comp.exceeds_cap
