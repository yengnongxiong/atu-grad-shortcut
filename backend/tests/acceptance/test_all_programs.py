"""Every ingested bachelor's program yields a feasible standard-pace plan from zero credit.

Guards the M6 sweep: 11 programs were once infeasible (corequisite alternatives, summer-only
courses), and a later data fetch briefly made Health Information Management infeasible.
"""

from __future__ import annotations

from collections import Counter

import pytest

from shortcut.data.loader import load_dataset
from shortcut.planner.service import plan_detailed
from shortcut.schemas.plan import PlanRequest

PROGRAM_IDS = sorted(load_dataset().programs)


@pytest.mark.parametrize("program_id", PROGRAM_IDS)
def test_program_plans_at_standard_pace(program_id: str) -> None:
    request = PlanRequest.model_validate(
        {"profile": {"program_id": program_id, "first_term": "2026FA", "math_act": 24}}
    )
    dataset = load_dataset()
    response = plan_detailed(dataset, request).response
    assert response.feasible, response.infeasible_reason
    assert response.totals["total_hours"] >= response.totals["required_total_hours"]
    assert response.graduation is not None and not response.graduation.id.endswith("WI")
    # A course is planned twice only when the map itself lists it twice (repeatable lessons,
    # or a map typo that validation already flags).
    listed = Counter(
        code
        for r in dataset.programs[program_id]["requirements"]
        if r["kind"] == "course"
        for code in {c for option in r["options"] for c in option}
    )
    planned = Counter(c.code for t in response.terms for c in t.courses if c.code)
    assert all(listed[code] >= count for code, count in planned.items() if count > 1)
