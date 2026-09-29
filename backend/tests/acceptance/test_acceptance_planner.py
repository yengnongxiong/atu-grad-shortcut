"""PRD §15 acceptance tests A1-A8 (planner, real 2025-26 CS data)."""

from __future__ import annotations

import json
from collections import Counter

from shortcut.data.loader import load_dataset
from shortcut.planner.exams import exam_opportunities
from shortcut.planner.service import plan_detailed
from shortcut.planner.terms import Term
from shortcut.planner.whatif import completed_credits, run_whatif
from shortcut.schemas.plan import PlanRequest, WhatIfRequest
from tests.acceptance.helpers import (
    A1_PROFILE,
    a1_plan,
    a1_request,
    a2_plan,
    earned_before,
    placements_by_code,
)
from tests.synthetic import REPO

APPENDIX_A = json.loads((REPO / "data" / "manual" / "appendix_a_cs_2025_26.json").read_text())


def test_a1_standard_pace_graduates_by_spring_2030_and_covers_appendix_a() -> None:
    detail = a1_plan()
    response = detail.response
    assert response.feasible, response.infeasible_reason
    assert response.graduation is not None
    assert Term.parse(response.graduation.id) <= Term.parse("2030SP")
    # Standard pace: fall/spring only, at most 16 hours.
    assert all(t.season in ("FA", "SP") and t.hours <= 16 for t in response.terms)
    # Every Appendix A course is scheduled.
    placed = placements_by_code(detail)
    for semester in APPENDIX_A["semesters"]:
        for row in semester["rows"]:
            if "code" in row:
                assert row["code"] in placed, row["code"]
    # Bucket rows: Social Sciences x2, Science with Lab x2, FA&H x2, U.S. Hist/Gov x1, electives x3.
    bucket_labels = Counter(
        c.label for t in response.terms for c in t.courses if c.kind in ("bucket", "elective")
    )
    assert bucket_labels["Social Sciences"] == 2
    assert bucket_labels["Science with Lab"] == 2
    assert bucket_labels["Fine Arts & Humanities"] == 2
    assert bucket_labels["U.S. History & Government"] == 1
    assert sum(n for label, n in bucket_labels.items() if "Elective" in label) == 3
    assert response.totals["total_hours"] >= 120
    assert response.totals["upper_level_hours"] >= 40


def test_a2_acceleration_is_strictly_earlier_than_a1() -> None:
    a1 = a1_plan().response
    a2 = a2_plan().response
    assert a2.feasible, a2.infeasible_reason
    assert a1.graduation is not None and a2.graduation is not None
    assert Term.parse(a2.graduation.id) < Term.parse(a1.graduation.id)
    assert (a2.terms_sooner_than_standard or 0) > 0
    enabled = [lv for lv in a2.levers if lv.enabled]
    assert {lv.id for lv in enabled} == {"heavier_terms", "summer", "winter", "overload"}
    assert any((lv.terms_saved or 0) > 0 for lv in enabled)


def test_a3_fall_only_and_spring_only_courses() -> None:
    for detail in (a1_plan(), a2_plan()):
        placed = placements_by_code(detail)
        for code in ("COMS 3213", "COMS 3703", "COMS 4103", "COMS 4913"):
            assert placed[code].season == "FA", (code, placed[code])
        assert placed["COMS 3313"].season == "SP"


def test_a4_ethics_needs_junior_standing() -> None:
    for detail in (a1_plan(), a2_plan()):
        term = placements_by_code(detail)["COMS 3053"]
        assert earned_before(detail, term) >= 60


def test_a5_clep_composition_59_removes_both_english_courses() -> None:
    profile = {
        **A1_PROFILE,
        "exams": [{"program": "CLEP", "exam": "College Composition", "score": 59}],
    }
    detail = plan_detailed(load_dataset(), PlanRequest.model_validate({"profile": profile}))
    placed = placements_by_code(detail)
    assert "ENGL 1013" not in placed and "ENGL 1023" not in placed
    credited = {c.code: c for c in detail.response.credited}
    assert credited["ENGL 1013"].source == "exam" and credited["ENGL 1023"].source == "exam"
    totals = detail.response.totals
    assert detail.full.state.exam_hours == 6  # counts toward the exam cap
    assert totals["exam_hours"] == 6
    assert totals["total_hours"] >= 120  # counts toward total hours
    assert totals["atu_hours"] == totals["planned_hours"]  # not toward residency
    assert detail.full.state.atu_hours == 0


def test_a6_no_term_exceeds_its_cap_and_first_term_at_most_18() -> None:
    policies = load_dataset().policies
    aggressive = PlanRequest.model_validate(
        {
            "profile": {**A1_PROFILE, "preferences": {"expect_high_gpa": True}},
            "levers": {
                "heavier_terms": True,
                "summer": True,
                "winter": True,
                "overload": True,
                "aggressive_overload": True,
            },
        }
    )
    plans = [a1_plan(), a2_plan(), plan_detailed(load_dataset(), aggressive)]
    for detail in plans:
        response = detail.response
        for term in response.terms:
            assert term.hours <= term.cap
            if term.season == "SU":
                assert term.hours <= policies.summer_max_load
            if term.season == "WI":
                assert term.hours <= policies.winter_max_hours
                assert len(term.courses) <= policies.winter_max_courses
            if term.season in ("FA", "SP"):
                assert term.hours <= policies.overload_ceiling
        first = response.terms[0]
        assert first.id == "2026FA" and first.hours <= policies.regular_load_max


def test_a7_fail_data_structures_matches_true_resolve() -> None:
    dataset = load_dataset()
    base = plan_detailed(dataset, a1_request().model_copy(update={"include_attribution": False}))
    item = next(i for i in base.full.build.items if i.code == "COMS 2213")
    index = base.full.result.placements[item.id].term_index
    term = base.full.result.slots[index].term
    whatif = run_whatif(
        dataset,
        WhatIfRequest(plan=a1_request(), event={"type": "fail", "code": "COMS 2213", "term": term.id}),
    )
    credits = completed_credits(base, index, also_in=index, exclude=item.id)
    manual = plan_detailed(
        dataset,
        a1_request().model_copy(update={"include_attribution": False}),
        plan_from=term.next(),
        extra_credits=credits,
    )
    assert whatif.after is not None and manual.response.graduation is not None
    assert whatif.after.id == manual.response.graduation.id
    assert whatif.before is not None
    assert Term.parse(whatif.after.id) >= Term.parse(whatif.before.id)
    retake = placements_by_code(manual)["COMS 2213"]
    assert retake > term
    assert "COMS 2213" in whatif.explanation
    assert whatif.after.label in whatif.explanation
    assert whatif.changed_terms


def test_a8_exam_opportunities_only_needed_and_ranked() -> None:
    dataset = load_dataset()
    persona = dataset.personas["p1"]
    request = PlanRequest.model_validate(persona["request"])
    response = exam_opportunities(dataset, request)
    assert response.opportunities, "P1 should have CLEP opportunities"
    base = plan_detailed(dataset, request.model_copy(update={"include_attribution": False}))
    needed: set[str] = set()
    for status in base.full.build.statuses:
        if status.satisfied:
            continue
        if status.req["kind"] == "course":
            needed.update(status.remaining_codes)
        else:
            needed.update(status.req["bucket"]["codes"])
    for opp in response.opportunities:
        assert set(opp.awards) & needed, opp.exam
        assert opp.requirements_satisfied
    keys = [(-(o.terms_saved or 0), -o.hours_saved) for o in response.opportunities if not o.exceeds_cap]
    assert keys == sorted(keys)
    # Exams that award nothing CS needs never appear (e.g. Human Growth & Development -> PSY 3813).
    assert all(o.exam != "Human Growth & Development" for o in response.opportunities)
