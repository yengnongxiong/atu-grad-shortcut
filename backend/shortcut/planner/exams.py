"""Exam opportunities (PRD F6) and click-to-delay impact (PRD F5), both via true re-solves."""

from __future__ import annotations

from typing import Any

from shortcut.data.loader import Dataset
from shortcut.planner.model import LeverState
from shortcut.planner.profile import course_hours
from shortcut.planner.service import (
    Outcome,
    PlanContext,
    hint_from,
    make_context,
    months_between,
    run_solve,
    term_ref,
)
from shortcut.planner.terms import terms_between
from shortcut.schemas.plan import (
    DelayRequest,
    DelayResponse,
    ExamOpportunitiesResponse,
    ExamOpportunity,
    PlanRequest,
    SourceLink,
)

PROGRAM_ORDER = {"CLEP": 0, "AP": 1, "IB": 2}


def needed_codes(outcome: Outcome) -> dict[str, tuple[str, float]]:
    """Codes that would satisfy a still-needed requirement: code -> (requirement label, hours).

    Exact course-code matches for course requirements, or a course listed in an unfilled
    bucket (PRD F6). Rule-based electives never count.
    """
    out: dict[str, tuple[str, float]] = {}
    for status in outcome.build.statuses:
        if status.satisfied:
            continue
        req = status.req
        if req["kind"] == "course":
            for code in status.remaining_codes:
                out.setdefault(code, (req["label"], float(req.get("hours") or 0)))
        else:
            for code in req["bucket"]["codes"]:
                out.setdefault(code, (req["label"], float(req.get("hours") or 0)))
    return out


def exam_opportunities(dataset: Dataset, request: PlanRequest) -> ExamOpportunitiesResponse:
    ctx = make_context(dataset, request)
    planned = list(request.levers.planned_exams)
    base = run_solve(ctx, ctx.levers, planned)
    held = {e.exam.lower() for e in request.profile.exams}
    cap = float(ctx.policies.exam_credit_cap_hours)
    exam_hours = base.state.exam_hours
    needed = needed_codes(base)
    rows: list[ExamOpportunity] = []
    for row in dataset.equivalencies():
        if row["exam"].lower() in held or row["id"] in planned:
            continue
        candidate = _evaluate_row(ctx, row, needed, base, planned, exam_hours, cap)
        if candidate is not None:
            rows.append(candidate)
    rows.sort(
        key=lambda r: (
            -(r.terms_saved or 0.0),
            -r.hours_saved,
            r.exceeds_cap,
            PROGRAM_ORDER.get(r.program, 9),
            r.exam,
            r.min_score,
        )
    )
    unavailable = [t["program"] for t in dataset.exams.values() if t.get("status") == "unavailable"]
    note = (
        "Only exams whose awarded courses exactly match a still-needed requirement are listed. "
        "Terms saved come from a full re-solve with that exam added."
    )
    if unavailable:
        note += f" {' and '.join(unavailable)} tables aren't available yet (see About the data)."
    return ExamOpportunitiesResponse(
        opportunities=rows,
        exam_hours_used=exam_hours,
        exam_cap_hours=cap,
        unavailable_programs=unavailable,
        note=note,
    )


def _evaluate_row(
    ctx: PlanContext,
    row: dict[str, Any],
    needed: dict[str, tuple[str, float]],
    base: Outcome,
    planned: list[str],
    exam_hours: float,
    cap: float,
) -> ExamOpportunity | None:
    best_option: list[str] | None = None
    best_useful: list[str] = []
    for option in row["awards"]:
        useful = [c for c in option if c in needed and not base.state.has(c)]
        if len(useful) > len(best_useful):
            best_option, best_useful = option, useful
    if not best_useful or best_option is None:
        return None
    labels: list[str] = []
    for code in best_useful:
        label = needed[code][0]
        if label not in labels:
            labels.append(label)
    hours_saved = sum(course_hours(ctx.dataset, c) for c in best_useful)
    award_hours = sum(course_hours(ctx.dataset, c) for c in best_option)
    exceeds = exam_hours + award_hours > cap
    terms_saved: float | None = None
    months: int | None = None
    base_grad = base.graduation
    if not exceeds and base_grad is not None:
        trial = run_solve(
            ctx,
            ctx.levers,
            [*planned, row["id"]],
            max_graduation_index=base.result.graduation_index,
            hint=hint_from(base),
        )
        if trial.graduation is not None:
            terms_saved = terms_between(trial.graduation, base_grad)
            months = months_between(ctx, trial.graduation, base_grad)
    source = row.get("source") or {}
    return ExamOpportunity(
        id=row["id"],
        program=row["program"],
        exam=row["exam"],
        min_score=float(row["min_score"]),
        awards=list(best_option),
        requirements_satisfied=labels,
        hours_saved=hours_saved,
        terms_saved=terms_saved,
        months_saved=months,
        exceeds_cap=exceeds,
        cap_note=(
            f"Would bring exam credit to {exam_hours + award_hours:g} of {cap:g} allowed hours."
            if exceeds
            else ""
        ),
        source=SourceLink(title=str(source.get("title", "")), url=str(source.get("url", ""))),
    )


def delay_impact(dataset: Dataset, request: DelayRequest) -> DelayResponse:
    """'What if I delay this one term?': forbid the course's current term or earlier, re-solve."""
    ctx = make_context(dataset, request.plan)
    planned = list(request.plan.levers.planned_exams)
    standard = run_solve(ctx, LeverState(), [])
    base = run_solve(
        ctx,
        ctx.levers,
        planned,
        max_graduation_index=standard.result.graduation_index,
        hint=hint_from(standard),
        phase="full",
    )
    if not base.result.feasible:
        raise ValueError("the current plan isn't feasible")
    item = next((i for i in base.build.items if i.id == request.item_id or i.code == request.item_id), None)
    if item is None:
        raise ValueError(f"{request.item_id} isn't in the plan")
    placement = base.result.placements[item.id]
    delayed = run_solve(
        ctx,
        ctx.levers,
        planned,
        min_term_index={item.id: placement.term_index + 1},
        hint=hint_from(base),
    )
    before = base.graduation
    after = delayed.graduation
    from_term = base.result.slots[placement.term_index].term
    to_term = None
    if delayed.result.feasible:
        to_term = delayed.result.slots[delayed.result.placements[item.id].term_index].term
    later = terms_between(before, after) if before and after else None
    if after is None:
        explanation = f"Delaying {item.label} past {from_term.label} leaves no valid plan."
    elif later is not None and later > 0.01:
        explanation = (
            f"Delaying {item.label} past {from_term.label} pushes graduation from "
            f"{before.label if before else '?'} to {after.label}: it's on the critical path."
        )
    else:
        explanation = (
            f"{item.label} can move past {from_term.label} without delaying graduation "
            f"({after.label}); it has slack."
        )
    return DelayResponse(
        item_id=item.id,
        label=item.label,
        from_term=term_ref(ctx, from_term),
        to_term=term_ref(ctx, to_term),
        before=term_ref(ctx, before),
        after=term_ref(ctx, after),
        terms_later=later,
        explanation=explanation,
    )
