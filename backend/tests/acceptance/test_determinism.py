"""PRD §9 determinism: the same request always returns the same schedule.

Parallel CP-SAT workers used to return a different tie-optimal schedule on each solve, so a
reload or a share link could move courses between terms while the date stayed the same.
"""

from __future__ import annotations

from shortcut.data.loader import load_dataset
from shortcut.planner.service import plan_detailed
from shortcut.schemas.plan import PlanRequest, PlanResponse


def schedule(response: PlanResponse) -> list[tuple[str, list[str]]]:
    return [(t.id, sorted(c.item_id for c in t.courses)) for t in response.terms]


def test_repeated_solves_return_the_same_schedule() -> None:
    dataset = load_dataset()
    request = PlanRequest.model_validate(dataset.personas["p1"]["request"])
    request.levers.heavier_terms = True
    request.levers.summer = True
    request.levers.winter = True
    runs = [schedule(plan_detailed(dataset, request).response) for _ in range(4)]
    assert all(run == runs[0] for run in runs[1:])
