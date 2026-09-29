"""Planner behaviour on small synthetic programs: prerequisites, coreqs, standing, caps, exams."""

from __future__ import annotations

from typing import Any

from shortcut.planner.service import plan_detailed
from shortcut.planner.terms import Term
from shortcut.schemas.plan import PlanRequest
from tests import synthetic as syn


def request(program_id: str = "test-program", **kwargs: Any) -> PlanRequest:
    profile = {"program_id": program_id, "first_term": "2026FA", "math_act": 30}
    profile.update(kwargs.pop("profile", {}))
    return PlanRequest.model_validate({"profile": profile, "levers": kwargs.pop("levers", {}), **kwargs})


def placed_terms(detail: Any) -> dict[str, Term]:
    result = detail.full.result
    items = {i.id: i for i in detail.full.build.items}
    out: dict[str, Term] = {}
    for item_id, placement in result.placements.items():
        key = items[item_id].code or item_id
        out[key] = result.slots[placement.term_index].term
    return out


def test_prerequisite_chain_is_strictly_ordered() -> None:
    courses = syn.chain("TST 1001", "TST 1002", "TST 2003", "TST 3004")
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])])
    detail = plan_detailed(ds, request())
    terms = placed_terms(detail)
    assert terms["TST 1001"] < terms["TST 1002"] < terms["TST 2003"] < terms["TST 3004"]
    assert detail.response.graduation is not None
    assert detail.response.graduation.id == "2028SP"  # four regular terms


def test_corequisites_share_a_term_or_come_earlier() -> None:
    lecture = syn.course("LAB 1013", coreqs=["LAB 1011"])
    lab = syn.course("LAB 1011", hours=1, coreqs=["LAB 1013"])
    later = syn.course("LAB 2013", prereq={"type": "course", "code": "LAB 1013", "min_grade": None})
    ds = syn.dataset(
        [lecture, lab, later],
        [syn.program([syn.req("LAB 1013"), syn.req("LAB 1011", hours=1), syn.req("LAB 2013")])],
    )
    terms = placed_terms(plan_detailed(ds, request()))
    assert terms["LAB 1013"] == terms["LAB 1011"]
    assert terms["LAB 2013"] > terms["LAB 1013"]


def test_or_prerequisite_uses_either_option() -> None:
    either = {
        "type": "or",
        "items": [
            {"type": "course", "code": "ORR 1001", "min_grade": None},
            {"type": "course", "code": "ORR 1002", "min_grade": None},
        ],
    }
    courses = [syn.course("ORR 1001"), syn.course("ORR 3003", prereq=either)]
    ds = syn.dataset(courses, [syn.program([syn.req("ORR 1001"), syn.req("ORR 3003")])])
    terms = placed_terms(plan_detailed(ds, request()))
    assert terms["ORR 3003"] > terms["ORR 1001"]


def test_standing_requires_cumulative_hours() -> None:
    fillers = [syn.course(f"FIL {1000 + i}") for i in range(24)]
    junior = syn.course("JRS 3001", standing="JR")
    reqs = [syn.req(c["code"]) for c in fillers] + [syn.req("JRS 3001")]
    ds = syn.dataset([*fillers, junior], [syn.program(reqs)])
    detail = plan_detailed(ds, request(profile={"preferences": {"preferred_hours": 15}}))
    result = detail.full.result
    items = {i.id: i for i in detail.full.build.items}
    jr_index = next(p.term_index for k, p in result.placements.items() if items[k].code == "JRS 3001")
    earned_before = sum(result.loads[:jr_index])
    assert earned_before >= syn.POLICIES.standing_thresholds["JR"]


def test_exam_credit_counts_toward_standing() -> None:
    """PRD §8 (assumed): class standing counts exam and transfer hours."""
    fillers = [syn.course(f"FIL {1000 + i}") for i in range(4)]
    junior = syn.course("JRS 3001", standing="JR")
    reqs = [syn.req(c["code"]) for c in fillers] + [syn.req("JRS 3001")]
    ds = syn.dataset([*fillers, junior], [syn.program(reqs)])
    transfer = [{"code": f"XFR {1000 + i}", "grade": "B", "source": "transfer"} for i in range(20)]
    detail = plan_detailed(ds, request(profile={"completed": transfer}))
    terms = placed_terms(detail)
    assert terms["JRS 3001"] == Term.parse("2026FA")


def test_fall_only_course_lands_in_fall() -> None:
    fall_only = syn.course("FAL 3003", offering=syn.offered(fall=True, spring=False))
    ds = syn.dataset(
        [syn.course("FAL 1001"), fall_only],
        [syn.program([syn.req("FAL 1001"), syn.req("FAL 3003")])],
    )
    detail = plan_detailed(ds, request(profile={"first_term": "2027SP"}))
    assert placed_terms(detail)["FAL 3003"].season == "FA"


def test_standard_pace_respects_preferred_hours() -> None:
    courses = [syn.course(f"CAP {1000 + i}") for i in range(12)]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])])
    detail = plan_detailed(ds, request(profile={"preferences": {"preferred_hours": 12}}))
    assert all(term.hours <= 12 for term in detail.response.terms)
    # 36 hours at 12 per fall/spring term: Fall 2026, Spring 2027, Fall 2027.
    assert detail.response.graduation is not None and detail.response.graduation.id == "2027FA"


def test_winter_and_summer_caps() -> None:
    courses = [
        syn.course(f"SHT {1000 + i}", offering=syn.offered(summer="derived", winter="derived"))
        for i in range(16)
    ]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])])
    detail = plan_detailed(ds, request(levers={"summer": True, "winter": True}))
    for term in detail.response.terms:
        if term.season == "WI":
            assert len(term.courses) <= syn.POLICIES.winter_max_courses
            assert term.hours <= syn.POLICIES.winter_max_hours
        if term.season == "SU":
            assert term.hours <= syn.POLICIES.summer_max_load


def test_first_term_never_overloaded() -> None:
    courses = [syn.course(f"OVR {1000 + i}") for i in range(20)]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])])
    detail = plan_detailed(
        ds,
        request(profile={"preferences": {"expect_high_gpa": True}}, levers={"aggressive_overload": True}),
    )
    first = detail.response.terms[0]
    assert first.id == "2026FA"
    assert first.hours <= syn.POLICIES.regular_load_max
    assert all(t.hours <= syn.POLICIES.overload_ceiling for t in detail.response.terms)


def test_overload_needs_eligibility() -> None:
    courses = [syn.course(f"OVR {1000 + i}") for i in range(20)]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])])
    detail = plan_detailed(ds, request(levers={"overload": True}))
    assert all(t.hours <= syn.POLICIES.regular_load_max for t in detail.response.terms)
    lever = next(lv for lv in detail.response.levers if lv.id == "overload")
    assert lever.available is False


def test_transfer_courses_only_in_summer_and_keep_residency() -> None:
    courses = [syn.course(f"TRN {1000 + i}", acts=f"ACTS {1000 + i}") for i in range(12)]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])])
    detail = plan_detailed(ds, request(levers={"transfer_summer": True}))
    transfers = [c for t in detail.response.terms for c in t.courses if c.transfer]
    for term in detail.response.terms:
        for c in term.courses:
            if c.transfer:
                assert term.season == "SU"
    assert transfers  # summer transfer is used to finish sooner
    atu_hours = detail.response.totals["atu_hours"]
    assert atu_hours >= syn.POLICIES.residency_min_hours


def test_exam_cap_warning_when_exceeded() -> None:
    courses = [syn.course(f"EXM {1000 + i}") for i in range(12)]
    rows = [
        {
            "id": f"clep-{i}",
            "program": "CLEP",
            "exam": f"Exam {i}",
            "min_score": 50,
            "awards": [[f"EXM {1000 + 3 * i}", f"EXM {1001 + 3 * i}", f"EXM {1002 + 3 * i}"]],
        }
        for i in range(4)
    ]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])], rows)
    exams = [{"program": "CLEP", "exam": f"Exam {i}", "score": 60} for i in range(4)]
    detail = plan_detailed(ds, request(profile={"exams": exams}))
    assert detail.full.state.exam_hours == 36
    ids = {w.id for w in detail.response.warnings}
    assert "exam-cap" in ids and "exam-gpa" in ids


def test_failed_course_is_not_credited() -> None:
    courses = syn.chain("FLD 1001", "FLD 2002")
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])])
    detail = plan_detailed(ds, request(profile={"completed": [{"code": "FLD 1001", "grade": "F"}]}))
    assert "FLD 1001" in placed_terms(detail)


def test_min_grade_blocks_prerequisite() -> None:
    needs_c = {"type": "course", "code": "GRD 1001", "min_grade": "C"}
    courses = [syn.course("GRD 1001"), syn.course("GRD 2002", prereq=needs_c)]
    ds = syn.dataset(courses, [syn.program([syn.req("GRD 1001"), syn.req("GRD 2002")])])
    detail = plan_detailed(ds, request(profile={"completed": [{"code": "GRD 1001", "grade": "D"}]}))
    assert "GRD 1001" in {i.code for i in detail.full.build.items}  # D doesn't meet a C prerequisite? retake
    terms = placed_terms(detail)
    assert terms["GRD 2002"] > terms["GRD 1001"]


def test_unofferable_course_explains_infeasibility() -> None:
    never = syn.course("NEV 3003", offering=syn.offered(fall=False, spring=False))
    ds = syn.dataset([never], [syn.program([syn.req("NEV 3003")])])
    detail = plan_detailed(ds, request())
    assert not detail.response.feasible
    assert "NEV 3003" in (detail.response.infeasible_reason or "")


def test_total_hours_filler_added() -> None:
    courses = [syn.course(f"TOT {1000 + i}") for i in range(4)]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses], total=18)])
    detail = plan_detailed(ds, request())
    assert detail.response.totals["total_hours"] >= 18
    assert any(i.kind == "filler" for i in detail.full.build.items)


def test_upper_level_filler_added() -> None:
    courses = [syn.course(f"UPL {1000 + i}") for i in range(4)]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses], total=12, upper=6)])
    detail = plan_detailed(ds, request())
    assert detail.response.totals["upper_level_hours"] >= 6


def test_summer_atu_and_transfer_both_enabled_places_every_item() -> None:
    """Regression: x and y share (item, term) keys when both summer levers are on."""
    offering = syn.offered(summer="derived")
    courses = [syn.course(f"BTH {1000 + i}", acts=f"ACTS {1000 + i}", offering=offering) for i in range(14)]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])])
    detail = plan_detailed(ds, request(levers={"summer": True, "transfer_summer": True}))
    placed = {c.code for t in detail.response.terms for c in t.courses}
    assert placed == {c["code"] for c in courses}
