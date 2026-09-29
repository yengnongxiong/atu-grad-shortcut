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


def test_repeated_or_requirement_schedules_each_option_once() -> None:
    """A map listing "ALT 1001 or ALT 1002" in two semesters means taking one of each."""
    courses = [syn.course("ALT 1001"), syn.course("ALT 1002")]
    first = {**syn.req("ALT 1001", semester=5), "id": "r-alt-5", "options": [["ALT 1001"], ["ALT 1002"]]}
    second = {**syn.req("ALT 1001", semester=6), "id": "r-alt-6", "options": [["ALT 1001"], ["ALT 1002"]]}
    ds = syn.dataset(courses, [syn.program([first, second])])
    detail = plan_detailed(ds, request())
    placed = sorted(c.code for t in detail.response.terms for c in t.courses if c.code)
    assert placed == ["ALT 1001", "ALT 1002"]


def test_repeated_or_requirement_with_credit_plans_the_other_option() -> None:
    courses = [syn.course("ALT 1001"), syn.course("ALT 1002")]
    first = {**syn.req("ALT 1001"), "id": "r-alt-a", "options": [["ALT 1001"], ["ALT 1002"]]}
    second = {**syn.req("ALT 1001"), "id": "r-alt-b", "options": [["ALT 1001"], ["ALT 1002"]]}
    ds = syn.dataset(courses, [syn.program([first, second])])
    completed = [{"code": "ALT 1002", "grade": "B", "term": "2026SP"}]
    detail = plan_detailed(ds, request(profile={"completed": completed}))
    placed = [c.code for t in detail.response.terms for c in t.courses if c.code]
    assert placed == ["ALT 1001"]


def test_corequisite_alternatives_need_only_one() -> None:
    """ "Co-requisite: SEED 4809 or SEED 4909" must not force both 9-hour residencies into one term."""
    seminar = syn.course("SEM 4503", coreq_options=[["RES 4809", "RES 4909"]])
    residency_a = syn.course("RES 4809", hours=9, coreqs=["SEM 4503"])
    residency_b = syn.course("RES 4909", hours=9, coreqs=["SEM 4503"])
    program = syn.program([syn.req("SEM 4503"), syn.req("RES 4909", hours=9)])
    ds = syn.dataset([seminar, residency_a, residency_b], [program])
    detail = plan_detailed(ds, request())
    assert detail.response.feasible
    terms = placed_terms(detail)
    assert "RES 4809" not in terms
    assert terms["SEM 4503"] == terms["RES 4909"]


def test_missing_corequisite_group_adds_first_alternative() -> None:
    lab = syn.course("LAB 2000", hours=1, coreq_options=[["PHY 2014", "PHY 2114"]])
    ds = syn.dataset(
        [lab, syn.course("PHY 2014", hours=4), syn.course("PHY 2114", hours=4)],
        [syn.program([syn.req("LAB 2000", hours=1)])],
    )
    detail = plan_detailed(ds, request())
    terms = placed_terms(detail)
    assert "PHY 2014" in terms and "PHY 2114" not in terms
    assert terms["PHY 2014"] <= terms["LAB 2000"]


def test_program_scoped_prerequisite_keeps_only_program_courses() -> None:
    """ "Completion of all HES, PE, and HLED courses" lists every concentration's courses."""
    all_courses = {
        "type": "and",
        "items": [{"type": "course", "code": c, "min_grade": None} for c in ("PRG 1001", "OTH 1001")],
    }
    internship = {**syn.course("PRG 4012", hours=12, prereq=all_courses), "prerequisite_scope": "program"}
    ds = syn.dataset(
        [internship, syn.course("PRG 1001"), syn.course("OTH 1001")],
        [syn.program([syn.req("PRG 1001"), syn.req("PRG 4012", hours=12)])],
    )
    detail = plan_detailed(ds, request())
    terms = placed_terms(detail)
    assert "OTH 1001" not in terms
    assert terms["PRG 1001"] < terms["PRG 4012"]


def test_summer_only_required_course_gets_a_summer_without_the_lever() -> None:
    field_camp = syn.course(
        "GEO 4006", hours=6, offering=syn.offered(fall=False, spring=False, summer="documented")
    )
    ds = syn.dataset(
        [field_camp, syn.course("GEO 1001")],
        [syn.program([syn.req("GEO 1001"), syn.req("GEO 4006", hours=6)])],
    )
    detail = plan_detailed(ds, request())
    assert detail.response.feasible
    terms = placed_terms(detail)
    assert terms["GEO 4006"].season == "SU"
    assert terms["GEO 1001"].season != "SU"
    assert any(w.id.startswith("summer-only") for w in detail.response.warnings)


def test_retake_for_a_grade_counts_hours_once_but_repeatables_keep_credit() -> None:
    comp = syn.req("ENG 1013", min_grade="C")
    lessons = [
        {**syn.req("MUS 1501", hours=1), "id": "r-lesson-1"},
        {**syn.req("MUS 1501", hours=1), "id": "r-lesson-2"},
    ]
    ds = syn.dataset(
        [syn.course("ENG 1013"), syn.course("MUS 1501", hours=1)], [syn.program([comp, *lessons], total=5)]
    )
    completed = [{"code": "ENG 1013", "grade": "D"}, {"code": "MUS 1501", "grade": "A"}]
    detail = plan_detailed(ds, request(profile={"completed": completed}))
    response = detail.response
    planned = sorted(c.code for t in response.terms for c in t.courses if c.code)
    assert planned == ["ENG 1013", "MUS 1501"]
    assert response.totals["credited_hours"] == 1  # the D no longer counts; the lesson does
    assert response.totals["total_hours"] == 5
    notes = {c.code: c.counts_toward for c in response.credited}
    assert notes["ENG 1013"] == "replaced by the planned retake"


def test_a_plan_never_graduates_in_winter_intersession() -> None:
    """ATU lists December, May and summer graduates only (academic calendar)."""
    courses = [syn.course(f"WIN {1000 + i}", offering=syn.offered(winter="derived")) for i in range(6)]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses])])
    detail = plan_detailed(ds, request(levers={"winter": True}))
    graduation = detail.response.graduation
    assert graduation is not None and not graduation.id.endswith("WI")
    assert detail.response.terms[-1].season != "WI"


def test_open_elective_slots_meet_the_upper_level_minimum_without_extra_hours() -> None:
    """Psychology regression (D17): 147 planned hours instead of 120."""
    courses = [syn.course(f"LOW {1000 + i}") for i in range(4)]
    slots = [syn.elective(f"r-gen-{i}", semester=8) for i in range(4)]
    program = syn.program([*(syn.req(c["code"]) for c in courses), *slots], total=24, upper=9)
    detail = plan_detailed(syn.dataset(courses, [program]), request())
    totals = detail.response.totals
    assert totals["total_hours"] == 24
    assert totals["upper_level_hours"] >= 9
    assert not any(i.kind == "filler" for i in detail.full.build.items)
    upper_slots = [i for i in detail.full.build.items if i.kind == "elective" and i.upper]
    assert len(upper_slots) == 3 and all("3000-4000" in i.label for i in upper_slots)
