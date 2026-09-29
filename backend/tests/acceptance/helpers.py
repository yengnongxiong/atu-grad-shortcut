"""Shared helpers for PRD §15 acceptance tests (run against data/processed)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from shortcut.data.loader import load_dataset
from shortcut.planner.service import DetailedPlan, plan_detailed
from shortcut.planner.terms import Term
from shortcut.schemas.plan import PlanRequest

CS = "computer-science-2025-26"

A1_PROFILE: dict[str, Any] = {
    "program_id": CS,
    "first_term": "2026FA",
    "plan_from": "2026FA",
    "math_act": 27,
    "preferences": {"preferred_hours": 16, "mode": "conservative"},
}
A2_LEVERS = {"heavier_terms": True, "summer": True, "winter": True, "overload": True}


def a1_request() -> PlanRequest:
    return PlanRequest.model_validate({"profile": A1_PROFILE})


def a2_request() -> PlanRequest:
    profile = {**A1_PROFILE, "preferences": {**A1_PROFILE["preferences"], "expect_high_gpa": True}}
    return PlanRequest.model_validate({"profile": profile, "levers": A2_LEVERS})


@lru_cache(maxsize=1)
def a1_plan() -> DetailedPlan:
    return plan_detailed(load_dataset(), a1_request())


@lru_cache(maxsize=1)
def a2_plan() -> DetailedPlan:
    return plan_detailed(load_dataset(), a2_request())


def placements_by_code(detail: DetailedPlan) -> dict[str, Term]:
    result = detail.full.result
    out: dict[str, Term] = {}
    for item in detail.full.build.items:
        if item.code:
            out[item.code] = result.slots[result.placements[item.id].term_index].term
    return out


def earned_before(detail: DetailedPlan, term: Term) -> float:
    result = detail.full.result
    base = detail.full.state.earned_hours
    return base + sum(load for slot, load in zip(result.slots, result.loads, strict=True) if slot.term < term)
