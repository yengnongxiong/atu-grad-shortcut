"""Every ATU catalog course resolves its real hours, not a 3-hour guess (PRD v1.1 §3.6)."""

from shortcut.data.loader import load_dataset
from shortcut.planner.profile import course_hours, course_known


def test_lab_outside_program_data_keeps_its_catalog_hours() -> None:
    ds = load_dataset()
    assert "WS 1091" not in ds.courses  # Fitness Walking/Jogging: in no program or exam table
    assert course_hours(ds, "WS 1091") == 1.0


def test_unknown_code_is_flagged() -> None:
    ds = load_dataset()
    assert course_known(ds, "COMS 1411")
    assert not course_known(ds, "ZZZZ 1234")


def test_plan_warns_about_codes_outside_the_catalog() -> None:
    from fastapi.testclient import TestClient

    from shortcut.api.app import create_app

    body = {
        "profile": {
            "program_id": "computer-science-2025-26",
            "first_term": "2026FA",
            "completed": [{"code": "ZZZZ 1234", "grade": "A", "source": "transfer"}],
        },
        "include_attribution": False,
    }
    warnings = TestClient(create_app()).post("/api/plan", json=body).json()["warnings"]
    unknown = [w for w in warnings if w["id"] == "unknown-course-ZZZZ 1234"]
    assert len(unknown) == 1
    assert "3 hours" in unknown[0]["message"]
