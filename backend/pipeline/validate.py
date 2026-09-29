"""Stage 7: validation checks (PRD §7.6) and trust tiers (PRD §7.5)."""

from __future__ import annotations

import re
from typing import Any

from pipeline.prereqs import tree_codes
from pipeline.programs import requirement_levels

CROSS_CHECKED = "cross_checked"
AUTO_IMPORTED = "auto_imported"
NEEDS_REVIEW = "needs_review"


def check(name: str, passed: bool, detail: str = "", severity: str = "error") -> dict[str, Any]:
    return {
        "check": name,
        "passed": passed,
        "severity": severity if not passed else "ok",
        "detail": detail,
    }


def validate_program(
    program: dict[str, Any],
    parsed_semesters: list[dict[str, Any]],
    courses: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    schedule = semesters_with_hours(program)
    results = [
        _semester_hours(schedule),
        _hours_inferred(program),
        _total_hours(program, parsed_semesters),
        _structure(program, parsed_semesters),
        _courses_resolve(program, courses),
        _prereqs_resolve(program, courses),
        _no_cycles(program, courses),
        _offering_flags(program, courses),
        _buckets_nonempty(program),
        _upper_level(program, courses),
        _repeats_consistent(program),
    ]
    return results


def _map_title_words(raw_text: str) -> set[str]:
    m = re.search(r"\d{4}\s*[-–]\s*(.+)", raw_text)
    words = re.findall(r"[a-z]+", (m.group(1) if m else "").lower())
    return {w for w in words if w not in {"of", "and", "the", "to", "in", "for", "i", "ii", "iii"}}


def _repeats_consistent(program: dict[str, Any]) -> dict[str, Any]:
    """The same course listed twice under different titles is a map typo (BIOL 2134 as both
    Principles of Botany and Principles of Zoology); repeatable courses keep one title."""
    by_code: dict[str, list[dict[str, Any]]] = {}
    for req in program["requirements"]:
        if req["kind"] == "course" and len(req["options"]) == 1 and len(req["options"][0]) == 1:
            by_code.setdefault(req["options"][0][0], []).append(req)
    problems: list[str] = []
    for code, reqs in by_code.items():
        titles = [_map_title_words(r["raw_text"]) for r in reqs]
        for req, other in zip(reqs[1:], titles[1:], strict=True):
            union = titles[0] | other
            if titles[0] and other and len(titles[0] & other) / len(union) < 0.5:
                problems.append(f"{code} is listed as both {reqs[0]['raw_text']!r} and {req['raw_text']!r}")
                break
    return check("repeated_courses_consistent", not problems, "; ".join(problems))


def semesters_with_hours(program: dict[str, Any]) -> list[dict[str, Any]]:
    """Map semesters with row hours after provenance-tracked inference (programs.py)."""
    by_id = {r["id"]: r for r in program["requirements"]}
    out = []
    for sem in program["map_schedule"]:
        rows = []
        for item in sem["items"]:
            req = by_id[item["requirement_id"]]
            low = req["hours"]
            high = req["hours_max"] if req["hours_max"] is not None else low
            rows.append({"hours_min": low, "hours_max": high})
        out.append(
            {
                "number": sem["semester"],
                "stated_total_text": sem["stated_total"],
                "stated_total_min": sem["stated_total_min"],
                "stated_total_max": sem["stated_total_max"],
                "rows": rows,
            }
        )
    return out


def _semester_hours(semesters: list[dict[str, Any]]) -> dict[str, Any]:
    problems: list[str] = []
    for sem in semesters:
        rows = sem["rows"]
        if any(r["hours_min"] is None for r in rows):
            problems.append(f"semester {sem['number']}: a row has no hours value")
            continue
        low = sum(r["hours_min"] for r in rows)
        high = sum(r["hours_max"] for r in rows)
        stated_low, stated_high = sem["stated_total_min"], sem["stated_total_max"]
        if stated_low is None:
            problems.append(f"semester {sem['number']}: no stated total")
        elif not (abs(low - stated_low) < 0.01 and abs(high - stated_high) < 0.01) and not (
            low <= stated_low and stated_high <= high and stated_low <= stated_high
        ):
            problems.append(
                f"semester {sem['number']}: rows sum to {_rng(low, high)} but the map states "
                f"{sem['stated_total_text']}"
            )
    return check("semester_hours_match", not problems, "; ".join(problems))


def _hours_inferred(program: dict[str, Any]) -> dict[str, Any]:
    inferred = [
        f"{r['id']} ({r['label']}): {r['hours']:g} from {r['hours_source'].replace('_', ' ')}"
        for r in program["requirements"]
        if r.get("hours_source") in ("catalog", "semester_total")
    ]
    return check("hours_inferred", True, "; ".join(inferred), severity="warning")


def _rng(low: float, high: float) -> str:
    return f"{low:g}" if low == high else f"{low:g}-{high:g}"


def _total_hours(program: dict[str, Any], semesters: list[dict[str, Any]]) -> dict[str, Any]:
    stated_high = sum((s["stated_total_max"] or 0) for s in semesters)
    rows_high = sum((r["hours_max"] or 0) for s in semesters for r in s["rows"])
    total = max(stated_high, rows_high)
    minimum = program["total_hours_min"]
    return check(
        "total_hours_meet_minimum",
        total + 0.01 >= minimum,
        f"map totals {total:g} vs required {minimum}",
    )


def _structure(program: dict[str, Any], semesters: list[dict[str, Any]]) -> dict[str, Any]:
    numbers = [s["number"] for s in semesters]
    expected = list(range(1, 9))
    ok = all(n in numbers for n in expected)
    low_conf = [r["id"] for r in program["requirements"] if r.get("confidence") == "low"]
    detail = []
    if not ok:
        detail.append(f"semesters found: {numbers}")
    if low_conf:
        detail.append(f"low-confidence rows: {', '.join(low_conf)}")
    return check("map_structure_parsed", ok and not low_conf, "; ".join(detail))


def _courses_resolve(program: dict[str, Any], courses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing = sorted(
        {
            c
            for r in program["requirements"]
            if r["kind"] == "course"
            for c in r["options"][0]
            if c not in courses or not courses[c]["in_catalog"]
        }
    )
    return check("required_courses_in_catalog", not missing, ", ".join(missing))


def _program_codes(program: dict[str, Any]) -> set[str]:
    return {c for r in program["requirements"] if r["kind"] == "course" for o in r["options"] for c in o}


def _prereqs_resolve(program: dict[str, Any], courses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    external: set[str] = set()
    unparsed: list[str] = []
    for code in _program_codes(program):
        course = courses.get(code)
        if not course:
            continue
        for dep in tree_codes(course["prerequisites"]):
            if dep not in courses or not courses[dep]["in_catalog"]:
                external.add(dep)
        if course["parse_confidence"] == "low":
            unparsed.append(code)
    detail = []
    if external:
        detail.append(f"flagged as external (not in catalog): {', '.join(sorted(external))}")
    if unparsed:
        detail.append(f"low-confidence prerequisite parse: {', '.join(sorted(unparsed))}")
    # Unresolved codes are flagged, not fatal (PRD §7.6); low-confidence parses are warnings.
    return check("prerequisites_resolve", True, "; ".join(detail), severity="warning")


def _satisfiable(tree: dict[str, Any] | None, done: set[str], program_codes: set[str]) -> bool:
    """Could this prerequisite tree be met once `done` courses are complete?

    Courses outside the program count as obtainable (they can be added as prerequisites);
    tests and standing are obtainable too. Only program courses create ordering constraints.
    """
    if tree is None:
        return True
    kind = tree["type"]
    if kind == "course":
        return tree["code"] not in program_codes or tree["code"] in done
    if kind == "and":
        return all(_satisfiable(t, done, program_codes) for t in tree["items"])
    if kind == "or":
        return any(_satisfiable(t, done, program_codes) for t in tree["items"])
    return True


def _no_cycles(program: dict[str, Any], courses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Hard cycles only: an OR-branch like 'BIOL 2124 or BIOL 2134 first' is not a cycle."""
    codes = {c for c in _program_codes(program) if c in courses}
    done: set[str] = set()
    changed = True
    while changed:
        changed = False
        for code in sorted(codes - done):
            if _satisfiable(courses[code]["prerequisites"], done, codes):
                done.add(code)
                changed = True
    stuck = sorted(codes - done)
    return check("no_prerequisite_cycles", not stuck, ", ".join(stuck))


def _offering_flags(program: dict[str, Any], courses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    conflicts = sorted(
        f"{c}: {courses[c]['offered'][s]['note']}"
        for c in _program_codes(program)
        if c in courses
        for s in ("FA", "SP")
        if courses[c]["offered"][s]["confidence"] == "conflicting"
    )
    unique = sorted(set(conflicts))
    return check(
        "offering_flags_agree",
        not unique,
        "; ".join(unique),
        severity="warning",
    )


def _buckets_nonempty(program: dict[str, Any]) -> dict[str, Any]:
    empty = [
        f"{r['id']} ({r['label']})"
        for r in program["requirements"]
        if r["kind"] == "bucket" and not r["bucket"]["codes"] and not r["bucket"]["rule"]
    ]
    return check("buckets_nonempty", not empty, ", ".join(empty))


def _upper_level(program: dict[str, Any], courses: dict[str, dict[str, Any]]) -> dict[str, Any]:
    upper = 0.0
    flexible = 0.0
    for req in program["requirements"]:
        hours = req["hours_max"] or req["hours"] or 0
        if requirement_levels(req, courses) >= 3000:
            upper += req["hours"] or 0
        elif _could_be_upper(req):
            flexible += hours
    need = program["upper_level_hours_min"]
    ok = upper + flexible + 0.01 >= need
    return check(
        "upper_level_achievable",
        ok,
        f"{upper:g} upper-division hours required + {flexible:g} flexible elective hours vs {need} needed",
    )


def _could_be_upper(req: dict[str, Any]) -> bool:
    """A requirement a student could meet with a 3000-4000 course (electives, alternatives)."""
    if req["kind"] == "course":
        return any(code.split(" ")[1][:1] in "34" for option in req["options"] for code in option)
    bucket = req["bucket"]
    rule = bucket.get("rule")
    if rule is not None:
        return rule.get("max_level") is None or int(rule["max_level"]) >= 3000
    return any(code.split(" ")[1][:1] in "34" for code in bucket.get("codes", []))


def assign_tier(results: list[dict[str, Any]], cross_check: dict[str, Any] | None) -> str:
    failed = [r for r in results if not r["passed"] and r["severity"] == "error"]
    if failed:
        return NEEDS_REVIEW
    if cross_check and cross_check.get("result") == "passed":
        return CROSS_CHECKED
    return AUTO_IMPORTED
