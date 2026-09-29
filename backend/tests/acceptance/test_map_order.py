"""Among equally fast plans, first-semester map courses stay in the first term (D10 tie-break).

Regression: the polish pass used 1-hour TECH 1001 (Orientation to the University) as filler
to pack terms to exactly 16 hours, pushing a freshman's orientation to their third term.
"""

from __future__ import annotations

from tests.acceptance.helpers import a1_plan, a2_plan, placements_by_code


def test_orientation_stays_in_the_first_term_at_standard_pace() -> None:
    assert placements_by_code(a1_plan())["TECH 1001"].id == "2026FA"


def test_orientation_stays_in_the_first_term_with_every_lever() -> None:
    assert placements_by_code(a2_plan())["TECH 1001"].id == "2026FA"


def test_calculus_stays_in_the_first_term_with_every_lever() -> None:
    """With a 27 math ACT, Calculus I (map semester 1, head of the critical chain) goes first."""
    assert placements_by_code(a1_plan())["MATH 2914"].id == "2026FA"
    assert placements_by_code(a2_plan())["MATH 2914"].id == "2026FA"
