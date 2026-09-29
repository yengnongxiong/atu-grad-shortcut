"""Every PRD §8 rule has at least one test (CLAUDE.md planner rules)."""

from __future__ import annotations

import json

from shortcut.planner.model import LeverState, SolveConfig, build_slots
from shortcut.planner.profile import _test_ok
from shortcut.planner.service import plan_detailed
from shortcut.planner.terms import Term, term_sequence
from shortcut.schemas.plan import PlanRequest
from tests import synthetic as syn

P = syn.POLICIES
RULES = json.loads((syn.REPO / "data" / "manual" / "policies.json").read_text())["rules"]


def config(levers: LeverState, **kwargs: object) -> SolveConfig:
    base: dict[str, object] = {
        "terms": term_sequence(Term.parse("2026FA"), 4),
        "mode": "conservative",
        "preferred_hours": 16,
        "levers": levers,
        "first_atu_term": Term.parse("2026FA"),
        "last_term_gpa": None,
        "expect_high_gpa": True,
    }
    base.update(kwargs)
    return SolveConfig(**base)  # type: ignore[arg-type]


def regular_slots(levers: LeverState, **kwargs: object) -> list[object]:
    return [s for s in build_slots(config(levers, **kwargs), P) if s.term.is_regular]


def test_policy_file_matches_prd_section_8() -> None:
    expected = {
        "regular_load_max": (18, "documented"),
        "overload_ceiling": (24, "documented"),
        "overload_review_threshold": (21, "documented"),
        "overload_gpa_min": (3.25, "documented"),
        "overload_prior_term_min_hours": (12, "documented"),
        "first_term_no_overload": (True, "derived"),
        "probation_advisor_threshold": (15, "documented"),
        "workload_outside_per_credit": ([2, 3], "documented"),
        "standing_thresholds": ({"FR": 0, "SO": 30, "JR": 60, "SR": 90}, "documented"),
        "residency_min_hours": (30, "documented"),
        "residency_upper_major_hours": (6, "documented"),
        "total_hours_min": (120, "documented"),
        "exam_credit_cap_hours": (30, "conflicting"),
        "math_placement_act_min": (27, "conflicting"),
        "summer_max_load": (12, "assumed"),
        "winter_max_courses": (1, "assumed"),
        "winter_max_hours": (4, "assumed"),
        "summer_single_term": (True, "assumed"),
        "eight_week_sessions_modeled": (False, "assumed"),
        "standing_counts_exam_transfer": (True, "assumed"),
    }
    for key, (value, confidence) in expected.items():
        assert RULES[key]["value"] == value, key
        assert RULES[key]["confidence"] == confidence, key
    for key, rule in RULES.items():
        assert rule["sources"], key
        assert rule["confidence"] in {"documented", "derived", "assumed", "unknown", "conflicting"}


def test_regular_load_max_and_heavier_terms() -> None:
    standard = regular_slots(LeverState())
    heavier = regular_slots(LeverState(heavier_terms=True))
    assert all(s.cap_max == 16 for s in standard)  # type: ignore[attr-defined]
    assert all(s.cap_max == P.regular_load_max for s in heavier)  # type: ignore[attr-defined]


def test_overload_ceiling_review_threshold_and_first_term() -> None:
    over = regular_slots(LeverState(overload=True))
    aggressive = regular_slots(LeverState(aggressive_overload=True))
    assert over[0].cap_max == P.regular_load_max  # type: ignore[attr-defined]  # first ATU term
    assert over[1].cap_max == P.overload_review_threshold  # type: ignore[attr-defined]
    assert aggressive[1].cap_max == P.overload_ceiling  # type: ignore[attr-defined]


def test_overload_eligibility_needs_gpa() -> None:
    ineligible = regular_slots(LeverState(overload=True), expect_high_gpa=False)
    assert all(s.cap_max <= P.regular_load_max for s in ineligible)  # type: ignore[attr-defined]
    later_start = regular_slots(
        LeverState(overload=True),
        first_atu_term=Term.parse("2025FA"),
        last_term_gpa=3.5,
        expect_high_gpa=False,
    )
    assert later_start[0].cap_max == P.overload_review_threshold  # type: ignore[attr-defined]


def test_summer_and_winter_planning_caps() -> None:
    slots = build_slots(config(LeverState(summer=True, winter=True)), P)
    summer = next(s for s in slots if s.term.season == "SU")
    winter = next(s for s in slots if s.term.season == "WI")
    assert summer.cap_max == P.summer_max_load
    assert winter.cap_max == P.winter_max_hours and winter.max_courses == P.winter_max_courses
    closed = build_slots(config(LeverState()), P)
    assert all(s.cap_max == 0 for s in closed if s.term.season == "WI")
    # A closed summer takes nothing but required courses offered only in summer (D13).
    closed_summers = [s for s in closed if s.term.season == "SU"]
    assert all(not s.atu_allowed and not s.transfer_allowed and s.season_only for s in closed_summers)


def test_terms_order_and_single_summer() -> None:
    fall, winter, spring, summer = (Term.parse(t) for t in ("2026FA", "2026WI", "2027SP", "2027SU"))
    assert fall < winter < spring < summer < Term.parse("2027FA")
    sequence = term_sequence(fall, 4)
    assert [t.id for t in sequence] == [
        "2026FA",
        "2026WI",
        "2027SP",
        "2027SU",
        "2027FA",
        "2027WI",
        "2028SP",
    ]
    assert winter.label == "Winter 2026–27"
    assert spring.end_label(P.term_end_months) == "May 2027"


def test_math_placement_uses_act_above_26() -> None:
    node = {"type": "test", "test": "ACT Math", "min_score": P.math_placement_act_min}
    assert _test_ok(node, 27) and not _test_ok(node, 26)
    assert _test_ok(node, None)  # not entered: placement assumed (D9)
    assert _test_ok({"type": "test", "test": "ACT English", "min_score": 19}, 20)


def test_math_ladder_is_ordered() -> None:
    assert P.math_ladder[0] == "MATH 1113"
    assert P.math_ladder.index("MATH 2914") < P.math_ladder.index("MATH 2924")


def _plan(**profile: object) -> object:
    courses = [syn.course(f"POL {1000 + i}") for i in range(6)]
    ds = syn.dataset(courses, [syn.program([syn.req(c["code"]) for c in courses], total=18)])
    base: dict[str, object] = {"program_id": "test-program", "first_term": "2026FA"}
    base.update(profile)
    return plan_detailed(ds, PlanRequest.model_validate({"profile": base}))


def test_workload_guidance_two_to_three_hours_per_credit() -> None:
    detail = _plan()
    low, high = P.workload_per_credit
    term = detail.response.terms[0]  # type: ignore[attr-defined]
    assert term.workload_low == term.hours * (1 + low)
    assert term.workload_high == term.hours * (1 + high)


def test_probation_warning_when_gpa_below_two() -> None:
    detail = _plan(preferences={"last_term_gpa": 1.8})
    assert any(w.id == "probation" for w in detail.response.warnings)  # type: ignore[attr-defined]


def test_residency_and_total_hours_reported() -> None:
    detail = _plan()
    totals = detail.response.totals  # type: ignore[attr-defined]
    assert totals["total_hours"] >= 18
    assert totals["atu_hours"] == totals["planned_hours"]
