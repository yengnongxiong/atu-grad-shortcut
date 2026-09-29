"""Stage 6: exam equivalency tables.

AP, IB, and CLEP come from the ATU catalog snapshots in data/raw/catalog (D23). If a snapshot
is missing, CLEP falls back to PRD Appendix B and AP/IB are marked unavailable (D6).
"""

from __future__ import annotations

import json
from typing import Any

from pipeline.catalog_tables import parse_exam_table
from pipeline.common import MANUAL_DIR, RAW_DIR, read_json

CATALOG_DIR = RAW_DIR / "catalog"
PROGRAMS = ("CLEP", "AP", "IB")
UNAVAILABLE = (
    "ATU's {program} table is published only on catalog.atu.edu and no snapshot of it is "
    "saved in data/raw/catalog. It is not guessed."
)
CATALOG_URLS = {
    p: f"https://catalog.atu.edu/undergraduate/institutional-credit/{p.lower()}/" for p in PROGRAMS
}


def _with_hours(row: dict[str, Any], courses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    option_hours: list[float | None] = []
    warnings: list[str] = []
    for option in row["awards"]:
        total: float | None = 0.0
        for code in option:
            course = courses.get(code)
            if course is None or course.get("hours") is None:
                warnings.append(f"{code} not found in the Banner catalog")
                total = None
                break
            total = (total or 0.0) + float(course["hours"])
        option_hours.append(total)
    return {**row, "award_hours": option_hours, "warnings": warnings}


def snapshot_rows(program: str) -> list[dict[str, Any]] | None:
    path = CATALOG_DIR / f"{program.lower()}.json"
    if not path.exists():
        return None
    return parse_exam_table(json.loads(path.read_text(encoding="utf-8")), program)


def appendix_b_rows() -> list[dict[str, Any]]:
    raw = read_json(MANUAL_DIR / "clep_appendix_b.json")
    return [
        {
            **row,
            "program": "CLEP",
            "generic_credit": None,
            "source": raw["source"],
            "confidence": "documented",
        }
        for row in raw["equivalencies"]
    ]


def appendix_b_diff(catalog: list[dict[str, Any]]) -> dict[str, list[str]]:
    """How the live CLEP table differs from the PRD's transcribed Appendix B."""
    old = {r["id"]: r["awards"] for r in appendix_b_rows()}
    new = {r["id"]: r["awards"] for r in catalog}
    return {
        "added": sorted(set(new) - set(old)),
        "removed": sorted(set(old) - set(new)),
        "changed": sorted(i for i in set(old) & set(new) if old[i] != new[i]),
    }


def exam_codes() -> set[str]:
    """Every course code any exam can award (so the pipeline builds those courses)."""
    rows = [r for p in PROGRAMS for r in (snapshot_rows(p) or [])] or appendix_b_rows()
    return {code for row in rows for option in row["awards"] for code in option}


def build_exam_tables(courses: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    tables: dict[str, dict[str, Any]] = {}
    for program in PROGRAMS:
        rows = snapshot_rows(program)
        source = {"title": f"ATU catalog: {program} credit", "url": CATALOG_URLS[program]}
        if rows is None and program == "CLEP":
            rows = appendix_b_rows()
            source = rows[0]["source"]
        if rows is None:
            tables[program.lower()] = {
                "program": program,
                "status": "unavailable",
                "note": UNAVAILABLE.format(program=program),
                "source": source,
                "equivalencies": [],
            }
            continue
        table: dict[str, Any] = {
            "program": program,
            "status": "available",
            "source": rows[0]["source"] if rows else source,
            "equivalencies": [_with_hours(row, courses) for row in rows],
        }
        if program == "CLEP" and snapshot_rows("CLEP") is not None:
            table["appendix_b_diff"] = appendix_b_diff(rows)
        tables[program.lower()] = table
    return tables
