"""What-if events (PRD F7): fail, drop, skip, change major. Each is a true re-solve."""

from __future__ import annotations

from dataclasses import dataclass

from shortcut.data.loader import Dataset
from shortcut.planner.profile import Credit, Item, slot_code
from shortcut.planner.service import DetailedPlan, plan_detailed
from shortcut.planner.terms import Term, terms_between
from shortcut.schemas.plan import (
    PlanRequest,
    PlanResponse,
    TermChange,
    WhatIfEvent,
    WhatIfRequest,
    WhatIfResponse,
)


class WhatIfError(ValueError):
    """The event doesn't apply to the plan (e.g. the course isn't in it)."""


@dataclass
class EventSetup:
    plan_from: Term | None
    credits: list[Credit]
    caps: dict[str, int]
    program_id: str | None
    event_term: Term | None


def completed_credits(
    base: DetailedPlan, before: int, also_in: int | None = None, exclude: str | None = None
) -> list[Credit]:
    """Planned work before term index `before` (and optionally in `also_in`), assumed passed."""
    credits: list[Credit] = []
    result = base.full.result
    for item in base.full.build.items:
        placement = result.placements[item.id]
        in_scope = placement.term_index < before or (also_in is not None and placement.term_index == also_in)
        if not in_scope or item.id == exclude:
            continue
        credits.append(_credit_for(item, "transfer" if placement.transfer else "assumed_pass"))
    return credits


def _credit_for(item: Item, source: str) -> Credit:
    code = item.code if item.code else slot_code(item.requirement_id or item.id)
    return Credit(
        code=code,
        title=item.title,
        hours=float(item.hours),
        source=source,
        grade="C",
        level=item.level,
    )


def find_item(base: DetailedPlan, code_or_id: str) -> Item:
    needle = code_or_id.strip().upper()
    for item in base.full.build.items:
        if item.id.upper() == needle or (item.code or "").upper() == needle:
            return item
    raise WhatIfError(f"{code_or_id} isn't in the current plan")


def setup_event(base: DetailedPlan, event: WhatIfEvent) -> EventSetup:
    result = base.full.result
    slots = result.slots
    if event.type == "change_major":
        if not event.program_id:
            raise WhatIfError("change_major needs program_id")
        return EventSetup(None, [], {}, event.program_id, None)
    if event.type == "fail":
        if not event.code:
            raise WhatIfError("fail needs a course code")
        item = find_item(base, event.code)
        index = result.placements[item.id].term_index
        if event.term and Term.parse(event.term) != slots[index].term:
            raise WhatIfError(f"{item.label} is planned for {slots[index].term.label}, not {event.term}")
        credits = completed_credits(base, index, also_in=index, exclude=item.id)
        return EventSetup(slots[index].term.next(), credits, {}, None, slots[index].term)
    if not event.term:
        raise WhatIfError(f"{event.type} needs a term")
    term = Term.parse(event.term)
    found = next((s.index for s in slots if s.term == term), None)
    if found is None:
        raise WhatIfError(f"{term.label} isn't in the plan's horizon")
    credits = completed_credits(base, found)
    hours = 0 if event.type == "skip" else int(event.hours if event.hours is not None else 0)
    if event.type == "drop" and event.hours is None:
        raise WhatIfError("drop needs hours")
    return EventSetup(term, credits, {term.id: hours}, None, term)


def run_whatif(dataset: Dataset, request: WhatIfRequest) -> WhatIfResponse:
    base_request = request.plan.model_copy(update={"include_attribution": False})
    base = plan_detailed(dataset, base_request)
    if not base.response.feasible:
        raise WhatIfError("the current plan isn't feasible, so there's nothing to compare")
    setup = setup_event(base, request.event)
    after = plan_detailed(
        dataset,
        base_request,
        plan_from=setup.plan_from,
        extra_credits=setup.credits,
        cap_overrides=setup.caps,
        program_id=setup.program_id,
    )
    return build_response(base, after, request.event, setup)


def build_response(
    base: DetailedPlan, after: DetailedPlan, event: WhatIfEvent, setup: EventSetup
) -> WhatIfResponse:
    before_grad = base.response.graduation
    after_grad = after.response.graduation
    later = None
    if before_grad and after_grad:
        later = terms_between(Term.parse(before_grad.id), Term.parse(after_grad.id))
    changes = changed_terms(base.response, after.response, setup.event_term)
    return WhatIfResponse(
        event=event,
        explanation=explain(base, after, event, later),
        before=before_grad,
        after=after_grad,
        terms_later=later,
        changed_terms=changes,
        plan=after.response,
    )


def changed_terms(before: PlanResponse, after: PlanResponse, since: Term | None) -> list[TermChange]:
    def by_term(plan: PlanResponse) -> dict[str, tuple[str, list[str]]]:
        return {t.id: (t.label, sorted(c.label for c in t.courses)) for t in plan.terms}

    old = by_term(before)
    new = by_term(after)
    ids = sorted(set(old) | set(new), key=lambda i: Term.parse(i))
    changes: list[TermChange] = []
    for term_id in ids:
        if since is not None and Term.parse(term_id) < since:
            continue
        old_courses = old.get(term_id, ("", []))[1]
        new_courses = new.get(term_id, ("", []))[1]
        if old_courses != new_courses:
            label = (new.get(term_id) or old.get(term_id) or (term_id, []))[0]
            changes.append(TermChange(term=term_id, label=label, before=old_courses, after=new_courses))
    return changes


def explain(base: DetailedPlan, after: DetailedPlan, event: WhatIfEvent, later: float | None) -> str:
    before_grad = base.response.graduation
    after_grad = after.response.graduation
    if not after.response.feasible or after_grad is None or before_grad is None:
        return f"After this change there is no valid plan: {after.response.infeasible_reason or ''}".strip()
    if event.type == "fail":
        subject = f"Failing {event.code}"
    elif event.type == "drop":
        subject = f"Dropping to {event.hours} hours in {Term.parse(event.term or '').label}"
    elif event.type == "skip":
        subject = f"Skipping {Term.parse(event.term or '').label}"
    else:
        name = after.response.program.name
        subject = f"Switching to {name}"
    if later is None or abs(later) < 0.01:
        impact = f"keeps graduation at {after_grad.label}"
    elif later > 0:
        impact = f"moves graduation from {before_grad.label} to {after_grad.label} ({_fmt(later)} later)"
    else:
        impact = f"moves graduation from {before_grad.label} to {after_grad.label} ({_fmt(-later)} sooner)"
    reason = _chain_reason(after, event)
    return f"{subject} {impact}." + (f" {reason}" if reason else "")


def _fmt(terms: float) -> str:
    whole = abs(terms - round(terms)) < 0.01
    value = f"{round(terms)}" if whole else f"{terms:g}"
    return f"{value} term{'s' if terms != 1 else ''}"


def _chain_reason(after: DetailedPlan, event: WhatIfEvent) -> str:
    """Name the critical chain that now sets the date, if any."""
    response = after.response
    if not response.critical_path:
        return ""
    labels = {n.id: (n.label, n.term, n.pattern) for n in response.graph_nodes}
    chain = [labels[i] for i in response.critical_path if i in labels][:6]
    parts = [f"{label} ({term}, offered {pattern or '—'})" for label, term, pattern in chain]
    lead = (
        "The retake starts a chain that now sets your date: "
        if event.type == "fail"
        else ("The chain that now sets your date: ")
    )
    return lead + " → ".join(parts) + "."


def rebase_request(request: PlanRequest) -> PlanRequest:
    return request.model_copy(update={"include_attribution": False})
