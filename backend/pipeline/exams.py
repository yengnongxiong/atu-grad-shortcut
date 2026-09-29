"""Stage 6: exam equivalency tables (CLEP from PRD Appendix B; AP/IB unavailable, see D6)."""

from __future__ import annotations

from typing import Any

from pipeline.common import MANUAL_DIR, read_json

AP_IB_UNAVAILABLE = (
    "ATU's AP and IB course tables are published only on catalog.atu.edu, which could not be "
    "reached from the build environment (WAF challenge). They are not guessed; add them to "
    "data/manual/ once transcribed."
)


def build_exam_tables(courses: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    clep_raw = read_json(MANUAL_DIR / "clep_appendix_b.json")
    source = clep_raw["source"]
    equivalencies: list[dict[str, Any]] = []
    for row in clep_raw["equivalencies"]:
        awards: list[list[str]] = row["awards"]
        option_hours: list[float | None] = []
        warnings: list[str] = []
        for option in awards:
            total = 0.0
            for code in option:
                course = courses.get(code)
                if course is None or course.get("hours") is None:
                    warnings.append(f"{code} not found in the Banner catalog")
                    total = float("nan")
                    break
                total += float(course["hours"])
            option_hours.append(None if total != total else total)
        equivalencies.append(
            {
                "id": row["id"],
                "program": "CLEP",
                "exam": row["exam"],
                "min_score": row["min_score"],
                "awards": awards,
                "award_hours": option_hours,
                "source": source,
                "confidence": "documented",
                "warnings": warnings,
            }
        )
    return {
        "clep": {
            "program": "CLEP",
            "status": "available",
            "source": source,
            "equivalencies": equivalencies,
        },
        "ap": {
            "program": "AP",
            "status": "unavailable",
            "note": AP_IB_UNAVAILABLE,
            "source": {
                "title": "ATU catalog: AP credit",
                "url": "https://catalog.atu.edu/undergraduate/institutional-credit/ap/",
            },
            "equivalencies": [],
        },
        "ib": {
            "program": "IB",
            "status": "unavailable",
            "note": AP_IB_UNAVAILABLE
            + " The IB Diploma rule (24 gen-ed hours) is recorded in policies.json.",
            "source": {
                "title": "ATU catalog: IB credit",
                "url": "https://catalog.atu.edu/undergraduate/institutional-credit/ib/",
            },
            "equivalencies": [],
        },
    }
