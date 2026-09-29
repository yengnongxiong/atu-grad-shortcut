"""CP-SAT planning model (PRD §9).

x[i, t] = item i taken at ATU in term t;  y[i, t] = item i transferred in (summer only).
Objective (lexicographic via weights): earliest graduation term, then fewest summer/winter
terms and overload hours, then closeness to preferred hours, then balanced loads.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from ortools.sat.python import cp_model

from shortcut.planner.policies import Policies
from shortcut.planner.profile import Item, StudentState, _test_ok, offered_ok
from shortcut.planner.terms import Term

SEED = 20260929
W_GRAD = 10_000_000
W_SHORT_TERM = 100_000
W_OVERLOAD_HOUR = 20_000
W_ABOVE_PREF = 400
W_MAX_LOAD = 80
W_ORDER = 1  # tie-break: keep courses near their degree-map semester


@dataclass(frozen=True)
class LeverState:
    heavier_terms: bool = False
    summer: bool = False
    winter: bool = False
    overload: bool = False
    aggressive_overload: bool = False
    transfer_summer: bool = False

    def without(self, lever: str) -> LeverState:
        return LeverState(**{**self.__dict__, lever: False})


@dataclass
class SolveConfig:
    terms: list[Term]
    mode: str
    preferred_hours: int
    levers: LeverState
    first_atu_term: Term
    last_term_gpa: float | None
    expect_high_gpa: bool
    time_limit_s: float = 5.0
    cap_overrides: dict[str, int] = field(default_factory=dict)
    min_term_index: dict[str, int] = field(default_factory=dict)
    max_graduation_index: int | None = None
    hint: dict[str, int] | None = None
    phase: str = "full"  # "graduation" (earliest term only) or "full" (also polish)
    polish_time_s: float = 1.2


@dataclass
class Slot:
    index: int
    term: Term
    cap_normal: int
    cap_max: int
    max_courses: int | None
    atu_allowed: bool
    transfer_allowed: bool
    overload_possible: bool


@dataclass
class Placement:
    item_id: str
    term_index: int
    transfer: bool


@dataclass
class SolveResult:
    status: str  # optimal | feasible | infeasible | unknown
    placements: dict[str, Placement]
    graduation_index: int | None
    loads: list[int]
    slots: list[Slot]
    wall_ms: int
    timed_out: bool
    unplaceable: list[str]

    @property
    def feasible(self) -> bool:
        return self.status in ("optimal", "feasible")


def build_slots(config: SolveConfig, policies: Policies) -> list[Slot]:
    lev = config.levers
    slots: list[Slot] = []
    for index, term in enumerate(config.terms):
        override = config.cap_overrides.get(term.id)
        if term.is_regular:
            heavier = lev.heavier_terms or lev.overload or lev.aggressive_overload
            cap_normal = policies.regular_load_max if heavier else config.preferred_hours
            cap_max = cap_normal
            if lev.aggressive_overload:
                cap_max = policies.overload_ceiling
            elif lev.overload:
                cap_max = policies.overload_review_threshold
            first_term = term == config.first_atu_term
            eligible = (
                config.expect_high_gpa
                if index > 0
                else (config.last_term_gpa is not None and config.last_term_gpa >= policies.overload_gpa_min)
            )
            if first_term and policies.first_term_no_overload:
                eligible = False
            if not eligible:
                cap_max = min(cap_max, max(cap_normal, 0))
            if first_term:
                cap_max = min(cap_max, policies.regular_load_max)
                cap_normal = min(cap_normal, cap_max)
            slot = Slot(
                index,
                term,
                cap_normal,
                cap_max,
                None,
                True,
                False,
                cap_max > policies.regular_load_max,
            )
        elif term.season == "SU":
            usable = lev.summer or lev.transfer_summer
            cap = policies.summer_max_load if usable else 0
            slot = Slot(index, term, cap, cap, None, lev.summer, lev.transfer_summer, False)
        else:
            cap = policies.winter_max_hours if lev.winter else 0
            slot = Slot(index, term, cap, cap, policies.winter_max_courses, lev.winter, False, False)
        if override is not None:
            slot.cap_normal = min(slot.cap_normal, override)
            slot.cap_max = min(slot.cap_max, override)
            slot.overload_possible = slot.overload_possible and slot.cap_max > policies.regular_load_max
        slots.append(slot)
    return slots


# ----------------------------------------------------------------------------- tree helpers


def simplify(
    tree: dict[str, Any] | None,
    state: StudentState,
    planned: dict[str, str],
) -> dict[str, Any] | bool:
    """Evaluate credited/test leaves; keep leaves for planned items (code -> item id)."""
    if tree is None:
        return True
    kind = tree["type"]
    if kind == "course":
        min_grade = "C" if tree.get("min_grade") == "C" else None
        if state.has(tree["code"], min_grade):
            return True
        if tree["code"] in planned:
            return {"type": "item", "id": planned[tree["code"]]}
        return False
    if kind == "test":
        return _test_ok(tree, state.math_act)
    if kind in ("and", "or"):
        parts = [simplify(t, state, planned) for t in tree["items"]]
        if kind == "and":
            if any(p is False for p in parts):
                return False
            rest: list[dict[str, Any] | bool] = [p for p in parts if p is not True]
            if not rest:
                return True
            return rest[0] if len(rest) == 1 else {"type": "and", "items": rest}
        if any(p is True for p in parts):
            return True
        remaining: list[dict[str, Any] | bool] = [p for p in parts if p is not False]
        if not remaining:
            return False
        return remaining[0] if len(remaining) == 1 else {"type": "or", "items": remaining}
    return True


def earliest_indices(
    items: Sequence[Item],
    trees: dict[str, dict[str, Any] | bool],
    allowed: dict[str, list[int]],
    coreq_ids: dict[str, list[str]],
) -> dict[str, int | None]:
    """Calendar-aware forward pass (ignores hour caps)."""
    inf = 10**6
    es: dict[str, int] = {i.id: inf for i in items}

    def ready(node: dict[str, Any] | bool) -> int:
        if node is True:
            return 0
        if node is False:
            return inf
        assert isinstance(node, dict)
        if node["type"] == "item":
            dep = es.get(node["id"], inf)
            return dep + 1 if dep < inf else inf
        values = [ready(n) for n in node["items"]]
        return max(values) if node["type"] == "and" else min(values)

    for _ in range(len(items) + 2):
        changed = False
        for item in items:
            bound = ready(trees[item.id])
            for coreq in coreq_ids.get(item.id, []):
                # Corequisites may share a term; an unresolved one (e.g. a mutual lab/lecture
                # pair) must not block the pass.
                if es.get(coreq, inf) < inf:
                    bound = max(bound, es[coreq])
            candidates = [t for t in allowed[item.id] if t >= bound]
            value = candidates[0] if candidates else inf
            if value != es[item.id]:
                es[item.id] = value
                changed = True
        if not changed:
            break
    return {k: (v if v < inf else None) for k, v in es.items()}


# ----------------------------------------------------------------------------- solve


def solve(
    items: Sequence[Item],
    state: StudentState,
    config: SolveConfig,
    policies: Policies,
) -> SolveResult:
    started = time.perf_counter()
    slots = build_slots(config, policies)
    planned = {i.code: i.id for i in items if i.code}
    trees = {i.id: simplify(i.prereq, state, planned) for i in items}
    coreq_ids = {i.id: [planned[c] for c in i.coreqs if c in planned and not state.has(c)] for i in items}

    allowed_atu: dict[str, list[int]] = {}
    allowed_tr: dict[str, list[int]] = {}
    max_index = len(slots) - 1
    if config.max_graduation_index is not None:
        max_index = min(max_index, config.max_graduation_index)
    for item in items:
        floor = config.min_term_index.get(item.id, 0)
        atu: list[int] = []
        tr: list[int] = []
        for slot in slots[: max_index + 1]:
            if slot.index < floor or (slot.cap_max <= 0 and item.hours > 0):
                continue
            if item.hours > slot.cap_max:
                continue
            season = slot.term.season
            if slot.atu_allowed and offered_ok(item.offered[season], config.mode):
                atu.append(slot.index)
            if slot.transfer_allowed and item.transferable:
                tr.append(slot.index)
        allowed_atu[item.id] = atu
        allowed_tr[item.id] = tr
    allowed = {i.id: sorted(set(allowed_atu[i.id]) | set(allowed_tr[i.id])) for i in items}
    es = earliest_indices(items, trees, allowed, coreq_ids)
    unplaceable = [i.id for i in items if es[i.id] is None or trees[i.id] is False]
    if unplaceable:
        return SolveResult("infeasible", {}, None, [], slots, _ms(started), False, unplaceable)

    model = cp_model.CpModel()
    x: dict[tuple[str, int], cp_model.IntVar] = {}
    y: dict[tuple[str, int], cp_model.IntVar] = {}
    by_item: dict[str, list[tuple[int, cp_model.IntVar]]] = {}
    for item in items:
        low = es[item.id] or 0
        entries: list[tuple[int, cp_model.IntVar]] = []
        for t in allowed_atu[item.id]:
            if t >= low:
                var = model.new_bool_var(f"x[{item.id}@{t}]")
                x[(item.id, t)] = var
                entries.append((t, var))
        for t in allowed_tr[item.id]:
            if t >= low:
                var = model.new_bool_var(f"y[{item.id}@{t}]")
                y[(item.id, t)] = var
                entries.append((t, var))
        if not entries:
            unplaceable.append(item.id)
        by_item[item.id] = entries
    if unplaceable:
        return SolveResult("infeasible", {}, None, [], slots, _ms(started), False, unplaceable)
    for item in items:
        model.add_exactly_one(var for _, var in by_item[item.id])

    def done_before(item_id: str, t: int) -> list[cp_model.IntVar]:
        return [var for s, var in by_item[item_id] if s < t]

    def done_by(item_id: str, t: int) -> list[cp_model.IntVar]:
        return [var for s, var in by_item[item_id] if s <= t]

    def encode(node: dict[str, Any] | bool, t: int, lit: cp_model.IntVar) -> None:
        if node is True:
            return
        if node is False:
            model.add(lit == 0)
            return
        assert isinstance(node, dict)
        if node["type"] == "item":
            model.add(sum(done_before(node["id"], t)) >= lit)
            return
        if node["type"] == "and":
            for child in node["items"]:
                encode(child, t, lit)
            return
        parts: list[Any] = []
        for child in node["items"]:
            if isinstance(child, dict) and child["type"] == "item":
                parts.extend(done_before(child["id"], t))
            else:
                aux = model.new_bool_var("or")
                encode(child, t, aux)
                parts.append(aux)
        model.add(sum(parts) >= lit)

    loads: list[Any] = []
    counts: list[Any] = []
    for slot in slots:
        terms_vars = [(item.hours, var) for item in items for (s, var) in by_item[item.id] if s == slot.index]
        loads.append(sum(h * v for h, v in terms_vars))
        counts.append(sum(v for _, v in terms_vars))

    base_hours = state.earned_hours if policies.standing_counts_exam_transfer else state.atu_hours
    thresholds = policies.standing_thresholds
    for item in items:
        tree = trees[item.id]
        for t, var in by_item[item.id]:
            encode(tree, t, var)
            for coreq in coreq_ids[item.id]:
                model.add(sum(done_by(coreq, t)) >= var)
            if item.standing:
                need = thresholds.get(item.standing, 0)
                if base_hours < need:
                    model.add(int(base_hours) + sum(loads[:t]) >= need).only_enforce_if(var)

    # Hour caps, overload eligibility, winter course count.
    over_hours: list[Any] = []
    short_used: list[Any] = []
    above_pref: list[Any] = []
    max_load = model.new_int_var(0, policies.overload_ceiling, "max_load")
    prev_regular: int | None = None
    for slot in slots:
        load = loads[slot.index]
        if slot.term.is_regular:
            if slot.overload_possible:
                over = model.new_bool_var(f"over@{slot.index}")
                model.add(load <= slot.cap_normal + (slot.cap_max - slot.cap_normal) * over)
                extra = model.new_int_var(0, policies.overload_ceiling, f"overh@{slot.index}")
                model.add(extra >= load - policies.regular_load_max)
                over_hours.append(extra)
                if prev_regular is not None:
                    model.add(loads[prev_regular] >= policies.overload_prior_term_min_hours).only_enforce_if(
                        over
                    )
            else:
                model.add(load <= slot.cap_normal)
            above = model.new_int_var(0, policies.overload_ceiling, f"abv@{slot.index}")
            model.add(above >= load - config.preferred_hours)
            above_pref.append(above)
            model.add(max_load >= load)
            prev_regular = slot.index
        else:
            model.add(load <= slot.cap_max)
            if slot.max_courses is not None:
                model.add(counts[slot.index] <= slot.max_courses)
            used = model.new_bool_var(f"used@{slot.index}")
            for item in items:
                for s, var in by_item[item.id]:
                    if s == slot.index:
                        model.add_implication(var, used)
            short_used.append(used)

    # Residency: transfer hours don't count toward ATU hours.
    if y:
        atu_planned = sum(
            item.hours * var for item in items for (s, var) in by_item[item.id] if (item.id, s) in x
        )
        need = policies.residency_min_hours - int(state.atu_hours)
        if need > 0:
            model.add(atu_planned >= need)

    grad = model.new_int_var(0, len(slots) - 1, "graduation")
    early: list[Any] = []
    for item in items:
        weight = order_weight(item)
        for t, var in by_item[item.id]:
            model.add(grad >= t * var)
            early.append(weight * t * var)

    _symmetry_breaking(model, items, by_item, trees)

    if config.hint:
        for item in items:
            hinted = config.hint.get(item.id)
            for t, var in by_item[item.id]:
                model.add_hint(var, 1 if t == hinted else 0)

    # Phase 1: earliest graduation term only (all attribution/exam re-solves need).
    model.minimize(grad)
    solver = _solver(config.time_limit_s)
    code = solver.solve(model)
    status = _status(code)
    if status not in ("optimal", "feasible"):
        return SolveResult(status, {}, None, [], slots, _ms(started), status == "unknown", [])
    timed_out = status == "feasible"
    best_grad = solver.value(grad)
    # x and y can share an (item, term) key (ATU vs. transfer in the same summer): keep both.
    all_vars = {("x", *key): var for key, var in x.items()} | {("y", *key): var for key, var in y.items()}
    values = {key: solver.value(var) for key, var in all_vars.items()}

    # Phase 2: hold the graduation term; polish summer/winter use, overloads, preferred
    # hours, balance, and map order within the remaining time budget.
    if config.phase == "full":
        model.add(grad == best_grad)
        model.clear_hints()  # type: ignore[no-untyped-call]
        for key, var in all_vars.items():
            model.add_hint(var, values[key])
        model.minimize(
            W_SHORT_TERM * sum(short_used)
            + W_OVERLOAD_HOUR * sum(over_hours)
            + W_ABOVE_PREF * sum(above_pref)
            + W_MAX_LOAD * max_load
            + W_ORDER * sum(early)
        )
        remaining = max(0.2, config.time_limit_s - (time.perf_counter() - started))
        polish = _solver(min(remaining, config.polish_time_s))
        polish_code = polish.solve(model)
        if _status(polish_code) in ("optimal", "feasible"):
            values = {key: polish.value(var) for key, var in all_vars.items()}

    placements: dict[str, Placement] = {}
    for (kind, item_id, t), value in values.items():
        if value:
            placements[item_id] = Placement(item_id, t, kind == "y")
    load_values = [
        sum(item.hours for item in items if placements[item.id].term_index == s.index) for s in slots
    ]
    return SolveResult(
        "feasible" if timed_out else "optimal",
        placements,
        best_grad,
        load_values,
        slots,
        _ms(started),
        timed_out,
        [],
    )


def _solver(limit_s: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = limit_s
    solver.parameters.random_seed = SEED
    solver.parameters.num_workers = 4
    return solver


def _status(code: Any) -> str:
    return {
        cp_model.OPTIMAL: "optimal",
        cp_model.FEASIBLE: "feasible",
        cp_model.INFEASIBLE: "infeasible",
    }.get(code, "unknown")


def order_weight(item: Item) -> int:
    """Earlier degree-map semesters pull harder toward the front of the plan."""
    if item.kind == "added_prereq":
        return 10
    if item.map_semester is None:
        return 1
    return max(1, 10 - item.map_semester)


def _symmetry_breaking(
    model: cp_model.CpModel,
    items: Sequence[Item],
    by_item: dict[str, list[tuple[int, cp_model.IntVar]]],
    trees: dict[str, dict[str, Any] | bool],
) -> None:
    """Interchangeable slots (same label/hours/offerings, no prereqs) are taken in order."""
    groups: dict[tuple[Any, ...], list[Item]] = {}
    for item in items:
        if item.code is not None or trees[item.id] is not True:
            continue
        key = (
            item.label,
            item.hours,
            item.level,
            item.transferable,
            tuple(sorted((s, e.get("available"), e.get("confidence")) for s, e in item.offered.items())),
        )
        groups.setdefault(key, []).append(item)
    for group in groups.values():
        for a, b in pairwise(group):
            pos_a = sum(t * v for t, v in by_item[a.id])
            pos_b = sum(t * v for t, v in by_item[b.id])
            model.add(pos_a <= pos_b)


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
