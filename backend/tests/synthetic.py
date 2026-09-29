"""Tiny in-memory datasets for planner unit tests (no pipeline output needed)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shortcut.data.loader import Dataset
from shortcut.planner.policies import Policies

REPO = Path(__file__).resolve().parents[2]
POLICIES = Policies(json.loads((REPO / "data" / "manual" / "policies.json").read_text()))


def offered(
    fall: bool = True,
    spring: bool = True,
    summer: str | None = None,
    winter: str | None = None,
) -> dict[str, dict[str, Any]]:
    def regular(on: bool) -> dict[str, Any]:
        return {"available": on, "confidence": "documented", "source": "test", "note": ""}

    def short(confidence: str | None) -> dict[str, Any]:
        if confidence is None:
            return {"available": False, "confidence": "documented", "source": "test", "note": ""}
        return {"available": True, "confidence": confidence, "source": "test", "note": ""}

    return {"FA": regular(fall), "SP": regular(spring), "SU": short(summer), "WI": short(winter)}


def course(
    code: str,
    hours: float = 3,
    prereq: dict[str, Any] | None = None,
    coreqs: list[str] | None = None,
    coreq_options: list[list[str]] | None = None,
    standing: str | None = None,
    offering: dict[str, dict[str, Any]] | None = None,
    acts: str | None = None,
) -> dict[str, Any]:
    number = code.split()[1]
    return {
        "code": code,
        "subject": code.split()[0],
        "number": number,
        "title": f"Course {code}",
        "hours": float(hours),
        "hours_max": None,
        "level": int(number[0]) * 1000,
        "upper_division": int(number[0]) >= 3,
        "college": "Test College",
        "department": "",
        "description": "",
        "prerequisites": prereq,
        "prereq_raw": "",
        "prereq_source": "test" if prereq else None,
        "parse_confidence": "high",
        "map_prereq_notes": [],
        "corequisites": [[c] for c in coreqs or []] + (coreq_options or []),
        "standing": standing,
        "standing_raw": "",
        "offered": offering or offered(),
        "history": {},
        "acts_equivalent": acts,
        "pass_fail": False,
        "gen_ed": False,
        "in_catalog": True,
        "warnings": [],
        "sources": [],
    }


def req(code: str, semester: int = 1, hours: float = 3, min_grade: str | None = None) -> dict[str, Any]:
    return {
        "id": f"r-{code.replace(' ', '')}",
        "kind": "course",
        "label": code,
        "options": [[code]],
        "hours": hours,
        "hours_max": None,
        "min_grade": min_grade,
        "map_semester": semester,
        "confidence": "high",
        "warnings": [],
        "notes": "",
        "raw_text": code,
    }


def bucket(req_id: str, label: str, codes: list[str], hours: float = 3, semester: int = 1) -> dict[str, Any]:
    return {
        "id": req_id,
        "kind": "bucket",
        "label": label,
        "bucket": {"category": "test", "codes": codes, "rule": None, "recommended": []},
        "hours": hours,
        "hours_max": None,
        "min_grade": None,
        "map_semester": semester,
        "confidence": "high",
        "warnings": [],
        "notes": "",
        "raw_text": label,
    }


def program(
    requirements: list[dict[str, Any]],
    total: float | None = None,
    upper: float = 0,
    program_id: str = "test-program",
    semesters: int = 8,
) -> dict[str, Any]:
    hours = sum(r["hours"] for r in requirements)
    return {
        "id": program_id,
        "name": "Test Program",
        "degree": "Bachelor of Science",
        "degree_abbr": "BS",
        "college": "Test College",
        "catalog_year": "2026-27",
        "total_hours_min": total if total is not None else hours,
        "upper_level_hours_min": upper,
        "gpa_min": 2.0,
        "requirements": requirements,
        "map_schedule": [{"semester": i + 1, "items": []} for i in range(semesters)],
        "trust_tier": "auto_imported",
        "validation": [],
        "admission_gates": [],
        "sources": [{"title": "test map", "url": "https://example.test/map.pdf"}],
    }


def dataset(
    courses: list[dict[str, Any]],
    programs: list[dict[str, Any]],
    equivalencies: list[dict[str, Any]] | None = None,
) -> Dataset:
    return Dataset(
        programs={p["id"]: p for p in programs},
        courses={c["code"]: c for c in courses},
        exams={"clep": {"program": "CLEP", "status": "available", "equivalencies": equivalencies or []}},
        policies=POLICIES,
        meta={},
        personas={},
        data_dir=REPO / "data",
    )


def chain(*codes: str) -> list[dict[str, Any]]:
    """Courses where each requires the previous one."""
    out = []
    previous: str | None = None
    for code in codes:
        prereq = {"type": "course", "code": previous, "min_grade": None} if previous else None
        out.append(course(code, prereq=prereq))
        previous = code
    return out


def elective(
    req_id: str, label: str = "General Elective", hours: float = 3, semester: int = 1
) -> dict[str, Any]:
    """An open elective slot with no level rule (the map's 'General Elective')."""
    rule = {"min_level": None, "max_level": None, "subjects": None, "approved": False, "general": True}
    return {
        **bucket(req_id, label, [], hours=hours, semester=semester),
        "bucket": {"category": "elective", "codes": [], "rule": rule, "recommended": []},
    }
