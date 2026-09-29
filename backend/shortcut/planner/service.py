"""High-level planning: standard pace, full plan, lever attribution, response assembly."""

from __future__ import annotations

import time
import zlib
from dataclasses import dataclass
from typing import Any

from shortcut.data.loader import Dataset
from shortcut.planner.model import LeverState, SolveConfig, SolveResult, solve
from shortcut.planner.policies import Policies
from shortcut.planner.profile import (
    Credit,
    ItemBuild,
    StudentState,
    build_items,
    build_state,
    is_math_test,
    offered_ok,
)
from shortcut.planner.slack import Edge, compute_slack
from shortcut.planner.terms import Term, nth_regular_after, term_sequence, terms_between
from shortcut.schemas.plan import (
    Baseline,
    CreditedCourse,
    GraphEdge,
    GraphNode,
    LeverResult,
    PlannedCourse,
    PlannedTerm,
    PlanRequest,
    PlanResponse,
    PlanStats,
    ProgramSummary,
    SourceLink,
    TermRef,
    Warning,
)

HORIZON_REGULAR_SEMESTERS = 16
LEVER_IDS = (
    "heavier_terms",
    "summer",
    "winter",
    "overload",
    "aggressive_overload",
    "transfer_summer",
)
BANNER_URL = "https://reg-prod.ec.atu.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=courseSearch"
SCHEDULE_URL = "https://reg-prod.ec.atu.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search"


# ----------------------------------------------------------------------------- context


@dataclass
class PlanContext:
    dataset: Dataset
    request: PlanRequest
    program: dict[str, Any]
    policies: Policies
    first_term: Term
    plan_from: Term
    terms: list[Term]
    preferred: int
    mode: str
    levers: LeverState
    solves: int = 0
    solve_ms: int = 0
    timed_out: bool = False
    extra_credits: list[Credit] | None = None
    cap_overrides: dict[str, int] | None = None

    @property
    def profile(self) -> Any:
        return self.request.profile


def make_context(dataset: Dataset, request: PlanRequest, plan_from: Term | None = None) -> PlanContext:
    profile = request.profile
    program = dataset.program(profile.program_id)
    policies = dataset.policies
    first = Term.parse(profile.first_term)
    start = plan_from or Term.parse(profile.plan_from or profile.first_term)
    if start < first:
        start = first
    lev = request.levers
    return PlanContext(
        dataset=dataset,
        request=request,
        program=program,
        policies=policies,
        first_term=first,
        plan_from=start,
        terms=term_sequence(start, HORIZON_REGULAR_SEMESTERS),
        preferred=profile.preferences.preferred_hours or policies.preferred_hours_default,
        mode=profile.preferences.mode,
        levers=LeverState(
            heavier_terms=lev.heavier_terms,
            summer=lev.summer,
            winter=lev.winter,
            overload=lev.overload,
            aggressive_overload=lev.aggressive_overload,
            transfer_summer=lev.transfer_summer,
        ),
    )


@dataclass
class Outcome:
    result: SolveResult
    build: ItemBuild
    state: StudentState
    levers: LeverState
    planned_exams: list[str]

    @property
    def graduation(self) -> Term | None:
        if not self.result.feasible or self.result.graduation_index is None:
            return None
        return self.result.slots[self.result.graduation_index].term


def run_solve(
    ctx: PlanContext,
    levers: LeverState,
    planned_exams: list[str],
    extra_credits: list[Credit] | None = None,
    cap_overrides: dict[str, int] | None = None,
    min_term_index: dict[str, int] | None = None,
    max_graduation_index: int | None = None,
    hint: dict[str, int] | None = None,
    program: dict[str, Any] | None = None,
    phase: str = "graduation",
) -> Outcome:
    credits = [*(ctx.extra_credits or []), *(extra_credits or [])]
    caps = {**(ctx.cap_overrides or {}), **(cap_overrides or {})}
    state = build_state(ctx.dataset, ctx.profile, planned_exams, credits)
    build = build_items(ctx.dataset, program or ctx.program, state, ctx.policies)
    prefs = ctx.profile.preferences
    config = SolveConfig(
        terms=ctx.terms,
        mode=ctx.mode,
        preferred_hours=ctx.preferred,
        levers=levers,
        first_atu_term=ctx.first_term,
        last_term_gpa=prefs.last_term_gpa,
        expect_high_gpa=prefs.expect_high_gpa,
        cap_overrides=caps,
        min_term_index=min_term_index or {},
        max_graduation_index=max_graduation_index,
        hint=hint,
        phase=phase,
    )
    started = time.perf_counter()
    result = solve(build.items, state, config, ctx.policies)
    ctx.solves += 1
    ctx.solve_ms += int((time.perf_counter() - started) * 1000)
    ctx.timed_out = ctx.timed_out or result.timed_out
    return Outcome(result, build, state, levers, planned_exams)


def hint_from(outcome: Outcome) -> dict[str, int] | None:
    if not outcome.result.feasible:
        return None
    return {k: p.term_index for k, p in outcome.result.placements.items()}


# ----------------------------------------------------------------------------- plan


def plan(dataset: Dataset, request: PlanRequest) -> PlanResponse:
    return plan_detailed(dataset, request).response


@dataclass
class DetailedPlan:
    response: PlanResponse
    ctx: PlanContext
    full: Outcome
    standard: Outcome


def plan_detailed(
    dataset: Dataset,
    request: PlanRequest,
    plan_from: Term | None = None,
    extra_credits: list[Credit] | None = None,
    cap_overrides: dict[str, int] | None = None,
    program_id: str | None = None,
) -> DetailedPlan:
    """Standard pace + full plan (+ attribution). Extra arguments support what-if re-solves."""
    if program_id is not None:
        profile = request.profile.model_copy(update={"program_id": program_id})
        request = request.model_copy(update={"profile": profile})
    ctx = make_context(dataset, request, plan_from)
    ctx.extra_credits = extra_credits
    ctx.cap_overrides = cap_overrides
    started = time.perf_counter()
    standard = run_solve(ctx, LeverState(), [])
    std_bound = standard.result.graduation_index if standard.result.feasible else None
    planned = list(request.levers.planned_exams)
    full = run_solve(
        ctx,
        ctx.levers,
        planned,
        max_graduation_index=std_bound,
        hint=hint_from(standard),
        phase="full",
    )
    lever_results = attribute_levers(ctx, full, standard) if request.include_attribution else []
    response = assemble(ctx, full, standard, lever_results)
    response.stats.solve_ms = int((time.perf_counter() - started) * 1000)
    return DetailedPlan(response, ctx, full, standard)


def attribute_levers(ctx: PlanContext, full: Outcome, standard: Outcome) -> list[LeverResult]:
    """Marginal terms saved: full plan vs. the same plan with only this lever off (PRD F4)."""
    results: list[LeverResult] = []
    full_grad = full.graduation
    bound = standard.result.graduation_index if standard.result.feasible else None
    eligible = _overload_eligible(ctx)
    for lever in (*LEVER_IDS, "planned_exams"):
        meta = LEVER_META[lever]
        enabled = bool(full.planned_exams) if lever == "planned_exams" else bool(getattr(ctx.levers, lever))
        saved: float | None = None
        months: int | None = None
        if enabled and full_grad is not None:
            if lever == "planned_exams":
                without = run_solve(ctx, full.levers, [], max_graduation_index=bound, hint=hint_from(full))
            else:
                without = run_solve(
                    ctx,
                    full.levers.without(lever),
                    full.planned_exams,
                    max_graduation_index=bound,
                    hint=hint_from(full),
                )
            if without.graduation is not None:
                saved = terms_between(full_grad, without.graduation)
                months = months_between(ctx, full_grad, without.graduation)
        available = True
        note = meta["note"]
        if lever in ("overload", "aggressive_overload") and not eligible:
            available = False
            note = (
                f"Needs a {ctx.policies.overload_gpa_min:.2f}+ GPA in the preceding term: check "
                "'I expect to keep a 3.25+ GPA' or enter your last-term GPA."
            )
        results.append(
            LeverResult(
                id=lever,
                label=meta["label"],
                enabled=enabled,
                available=available,
                terms_saved=saved,
                months_saved=months,
                cost=meta["cost"],
                approval=meta["approval"],
                workload=meta["workload"],
                note=note,
            )
        )
    return results


LEVER_META: dict[str, dict[str, Any]] = {
    "heavier_terms": {
        "label": "Heavier regular terms (up to 18 hrs)",
        "cost": "none",
        "approval": "none",
        "workload": "up to 18 hrs/term: about 54–72 hrs/week",
        "note": "No petition needed up to 18 hours.",
    },
    "summer": {
        "label": "Summer terms",
        "cost": "extra tuition",
        "approval": "none",
        "workload": "compressed sessions (May, June/July, 10-week, July/Aug)",
        "note": "Planning cap per summer from policies.json.",
    },
    "winter": {
        "label": "Winter intersession",
        "cost": "extra tuition",
        "approval": "none",
        "workload": "one intensive course over about three weeks",
        "note": "Mid-December to New Year's.",
    },
    "overload": {
        "label": "Overloads (19–21 hrs)",
        "cost": "none",
        "approval": "dean petition",
        "workload": "19–21 hrs/term: about 57–84 hrs/week",
        "note": "Dean petition; 3.25 GPA in the preceding term on 12+ ATU hours.",
    },
    "aggressive_overload": {
        "label": "Aggressive overloads (22–24 hrs)",
        "cost": "none",
        "approval": "dean petition + Academic Affairs",
        "workload": "22–24 hrs/term: about 66–96 hrs/week",
        "note": "Loads over 21 hours are flagged for Academic Affairs review.",
    },
    "transfer_summer": {
        "label": "Transfer summer courses (Arkansas public college)",
        "cost": "extra tuition",
        "approval": "advisor",
        "workload": "summer course elsewhere; ACTS-equivalent lower-level only",
        "note": "Transfer hours count toward total hours, not ATU residency.",
    },
    "planned_exams": {
        "label": "Planned exams (from Exam opportunities)",
        "cost": "exam fee",
        "approval": "none",
        "workload": "self-study for each exam",
        "note": "Exam credit doesn't count in GPA.",
    },
}


def _overload_eligible(ctx: PlanContext) -> bool:
    prefs = ctx.profile.preferences
    return prefs.expect_high_gpa or (
        prefs.last_term_gpa is not None and prefs.last_term_gpa >= ctx.policies.overload_gpa_min
    )


def months_between(ctx: PlanContext, earlier: Term, later: Term) -> int:
    order = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]
    ends = ctx.policies.term_end_months

    def month_index(term: Term) -> int:
        month = order.index(ends[term.season]) + 1
        year = term.year + 1 if term.season == "WI" else term.year
        return year * 12 + month

    return month_index(later) - month_index(earlier)


# ----------------------------------------------------------------------------- assembly


def term_ref(ctx: PlanContext, term: Term | None) -> TermRef | None:
    if term is None:
        return None
    return TermRef(id=term.id, label=term.label, date_label=term.end_label(ctx.policies.term_end_months))


def program_summary(program: dict[str, Any]) -> ProgramSummary:
    return ProgramSummary(
        id=program["id"],
        name=program["name"],
        degree=program["degree"],
        degree_abbr=program.get("degree_abbr", ""),
        college=program.get("college", ""),
        catalog_year=program["catalog_year"],
        trust_tier=program["trust_tier"],
        total_hours_min=float(program["total_hours_min"]),
        upper_level_hours_min=float(program["upper_level_hours_min"]),
    )


def degree_map_graduation(ctx: PlanContext) -> Term:
    """The term the degree map finishes in: its last regular semester, or the summer after it
    when the map ends with a summer block (Health Information Management)."""
    schedule = ctx.program["map_schedule"]
    regular = [s for s in schedule if not s.get("season")]
    term = nth_regular_after(ctx.first_term, len(regular) or 8)
    if schedule and schedule[-1].get("season") == "SU":
        while term.season != "SU":
            term = term.next()
    return term


def assemble(ctx: PlanContext, full: Outcome, standard: Outcome, levers: list[LeverResult]) -> PlanResponse:
    degree_map_term = degree_map_graduation(ctx)
    regular = [s for s in ctx.program["map_schedule"] if not s.get("season")]
    summers = len(ctx.program["map_schedule"]) - len(regular)
    degree_map = Baseline(
        graduation=term_ref(ctx, degree_map_term),
        note=f"The degree map's {len(regular)} semesters{' and its summer block' if summers else ''} counted "
        f"from {ctx.first_term.label}, assuming no prior credit.",
    )
    std_grad = standard.graduation
    standard_pace = Baseline(
        graduation=term_ref(ctx, std_grad),
        note=f"Fall/spring only, at most {ctx.preferred} hours per term, with your existing credit.",
    )
    warnings: list[Warning] = []
    assumptions = base_assumptions(ctx, full)
    result = full.result
    if not result.feasible:
        reason = explain_infeasible(ctx, full)
        warnings.append(Warning(id="infeasible", severity="error", category="plan", message=reason))
        return PlanResponse(
            program=program_summary(ctx.program),
            feasible=False,
            infeasible_reason=reason,
            graduation=None,
            degree_map=degree_map,
            standard_pace=standard_pace,
            terms_sooner_than_map=None,
            terms_sooner_than_standard=None,
            months_sooner_than_standard=None,
            terms=[],
            credited=credited_list(ctx, full),
            levers=levers,
            critical_path=[],
            graph_nodes=[],
            graph_edges=[],
            warnings=warnings + data_warnings(ctx, full, []),
            assumptions=assumptions,
            totals={},
            stats=PlanStats(
                solve_ms=ctx.solve_ms,
                solves=ctx.solves,
                status=result.status,
                timed_out=ctx.timed_out,
            ),
        )
    grad_index = result.graduation_index or 0
    grad = result.slots[grad_index].term
    slack, edges = compute_slack(
        full.build.items, full.state, result.placements, result.slots, grad_index, ctx.mode
    )
    critical = {k for k, v in slack.items() if v <= 0.0}
    terms = planned_terms(ctx, full, slack, critical)
    placed_ids = [i.id for i in sorted(full.build.items, key=lambda i: result.placements[i.id].term_index)]
    critical_path = [i for i in placed_ids if i in critical and _on_chain(i, edges, critical)]
    warnings += policy_warnings(ctx, full, terms)
    warnings += data_warnings(ctx, full, terms)
    sooner_std = terms_between(grad, std_grad) if std_grad else None
    no_gain = sooner_std is not None and sooner_std < 0.01
    return PlanResponse(
        program=program_summary(ctx.program),
        feasible=True,
        graduation=term_ref(ctx, grad),
        degree_map=degree_map,
        standard_pace=standard_pace,
        terms_sooner_than_map=terms_between(grad, degree_map_term),
        terms_sooner_than_standard=sooner_std,
        months_sooner_than_standard=months_between(ctx, grad, std_grad) if std_grad else None,
        pace_note=pace_note(ctx, full, critical_path, edges, terms_between(grad, degree_map_term))
        if no_gain
        else None,
        terms=terms,
        credited=credited_list(ctx, full),
        levers=levers,
        critical_path=critical_path,
        critical_chain=longest_chain(critical_path, edges, result.placements),
        graph_nodes=graph_nodes(ctx, full, slack, critical),
        graph_edges=[
            GraphEdge(
                source=e.source,
                target=e.target,
                kind=e.kind,
                critical=e.source in critical and e.target in critical,
            )
            for e in edges
        ],
        warnings=warnings,
        assumptions=assumptions,
        totals=totals(ctx, full),
        stats=PlanStats(
            solve_ms=ctx.solve_ms, solves=ctx.solves, status=result.status, timed_out=ctx.timed_out
        ),
    )


def pace_note(
    ctx: PlanContext,
    outcome: Outcome,
    critical_path: list[str],
    edges: list[Edge],
    sooner_than_map: float | None,
) -> str | None:
    """Explain what fixes the date when the levers that are on don't move it (PRD P4: say so
    honestly), or when a student is behind the degree map."""
    enabled = any(getattr(ctx.levers, name) for name in LEVER_META if hasattr(ctx.levers, name))
    enabled = enabled or bool(ctx.request.levers.planned_exams)
    behind = sooner_than_map is not None and sooner_than_map < -0.01
    if not (enabled or behind):
        return None
    items = {i.id: i for i in outcome.build.items}
    placements = outcome.result.placements
    slots = outcome.result.slots
    path = longest_chain(critical_path, edges, placements)
    if len(path) < 2:
        return None
    steps = [
        f"{items[i].label} ({slots[placements[i].term_index].term.label}, "
        f"offered {items[i].pattern(ctx.mode) or '—'})"
        for i in path
    ]
    chain = [items[i] for i in path]
    short_terms = any(offered_ok(i.offered[s], ctx.mode) for i in chain for s in ("SU", "WI"))
    if not enabled:
        return (
            f"At standard pace your date is set by a prerequisite chain: "
            f"{' → '.join(steps)}. Turn on levers, or try the What-if tab, to test recovery options."
        )
    note = (
        "None of the levers you turned on moves graduation. Your date is set by a prerequisite chain: "
        f"{' → '.join(steps)}."
    )
    if not short_terms:
        note += (
            " None of these courses has a confirmed summer or winter section, and each waits for the one"
            " before it, so extra terms and heavier loads can't run the chain faster."
        )
    return note


def longest_chain(critical_path: list[str], edges: list[Edge], placements: dict[str, Any]) -> list[str]:
    """The longest run of prerequisite edges through critical items, earliest first."""
    critical = set(critical_path)
    preds: dict[str, list[str]] = {}
    for edge in edges:
        if edge.kind == "prereq" and edge.source in critical and edge.target in critical:
            preds.setdefault(edge.target, []).append(edge.source)
    depth: dict[str, int] = {}
    for item_id in sorted(critical_path, key=lambda i: placements[i].term_index):
        depth[item_id] = 1 + max((depth.get(p, 0) for p in preds.get(item_id, [])), default=0)
    if not depth:
        return []
    end = max(depth, key=lambda i: (depth[i], placements[i].term_index))
    path = [end]
    while preds.get(path[-1]):
        path.append(max(preds[path[-1]], key=lambda i: depth.get(i, 0)))
    return list(reversed(path))


def _on_chain(item_id: str, edges: list[Edge], critical: set[str]) -> bool:
    """Critical items that are part of a prerequisite chain (not isolated slack-0 fillers)."""
    return any(
        (e.source == item_id and e.target in critical) or (e.target == item_id and e.source in critical)
        for e in edges
    )


def planned_terms(
    ctx: PlanContext, outcome: Outcome, slack: dict[str, float], critical: set[str]
) -> list[PlannedTerm]:
    result = outcome.result
    grad_index = result.graduation_index or 0
    policies = ctx.policies
    low, high = policies.workload_per_credit
    by_term: dict[int, list[PlannedCourse]] = {}
    for item in outcome.build.items:
        placement = result.placements[item.id]
        slot = result.slots[placement.term_index]
        entry = item.offered[slot.term.season]
        confidence = "derived" if placement.transfer else str(entry.get("confidence", "assumed"))
        low_conf = confidence == "unknown" or (
            not slot.term.is_regular and confidence == "assumed" and not placement.transfer
        )
        by_term.setdefault(placement.term_index, []).append(
            PlannedCourse(
                item_id=item.id,
                code=item.code,
                label=item.label,
                title=item.title,
                hours=item.hours,
                kind=item.kind,
                requirement_id=item.requirement_id,
                transfer=placement.transfer,
                critical=item.id in critical,
                slack=slack.get(item.id),
                offering_confidence=confidence,
                offering_note=(
                    "taken as ACTS transfer credit at another Arkansas public college (availability assumed)"
                    if placement.transfer
                    else str(entry.get("note", ""))
                ),
                low_confidence=low_conf,
                options=item.options,
                min_grade=item.min_grade,
            )
        )
    terms: list[PlannedTerm] = []
    for slot in result.slots[: grad_index + 1]:
        courses = sorted(by_term.get(slot.index, []), key=lambda c: (not c.critical, c.label))
        if not courses and not slot.term.is_regular:
            continue
        hours = float(sum(c.hours for c in courses))
        approval = None
        if hours > policies.overload_review_threshold:
            approval = "Dean petition + Academic Affairs review"
        elif hours > policies.regular_load_max:
            approval = "Dean petition (overload)"
        terms.append(
            PlannedTerm(
                id=slot.term.id,
                label=slot.term.label,
                season=slot.term.season,
                hours=hours,
                cap=float(slot.cap_max),
                courses=courses,
                workload_low=hours * (1 + low),
                workload_high=hours * (1 + high),
                overload=hours > policies.regular_load_max,
                approval=approval,
            )
        )
    return terms


def credited_list(ctx: PlanContext, outcome: Outcome) -> list[CreditedCourse]:
    out: list[CreditedCourse] = []
    for status in outcome.build.statuses:
        for credit in status.credited:
            out.append(
                CreditedCourse(
                    code=credit.code,
                    title=credit.title,
                    hours=credit.hours,
                    source=credit.source,
                    grade=credit.grade,
                    requirement_id=status.req["id"],
                    counts_toward=status.req["label"],
                )
            )
    for credit in outcome.state.credits.values():
        if credit.retaken:
            out.append(
                CreditedCourse(
                    code=credit.code,
                    title=credit.title,
                    hours=credit.hours,
                    source=credit.source,
                    grade=credit.grade,
                    requirement_id=None,
                    counts_toward="replaced by the planned retake",
                )
            )
    for credit in outcome.build.extra_credits:
        out.append(
            CreditedCourse(
                code=credit.code,
                title=credit.title,
                hours=credit.hours,
                source=credit.source,
                grade=credit.grade,
                requirement_id=None,
                counts_toward="total hours (no matching requirement)",
            )
        )
    return out


def graph_nodes(
    ctx: PlanContext, outcome: Outcome, slack: dict[str, float], critical: set[str]
) -> list[GraphNode]:
    result = outcome.result
    nodes: list[GraphNode] = []
    for item in outcome.build.items:
        placement = result.placements[item.id]
        slot = result.slots[placement.term_index]
        nodes.append(
            GraphNode(
                id=item.id,
                label=item.label,
                title=item.title,
                term=slot.term.label,
                term_index=placement.term_index,
                slack=slack.get(item.id),
                critical=item.id in critical,
                pattern=item.pattern(ctx.mode),
                hours=item.hours,
            )
        )
    return nodes


def totals(ctx: PlanContext, outcome: Outcome) -> dict[str, float]:
    state = outcome.state
    items = outcome.build.items
    placements = outcome.result.placements
    planned = float(sum(i.hours for i in items))
    transfer = float(sum(i.hours for i in items if placements[i.id].transfer))
    upper = float(sum(i.hours for i in items if i.upper))
    upper += float(sum(c.hours for c in state.credits.values() if c.counts_toward_degree and c.level >= 3000))
    return {
        "credited_hours": state.earned_hours,
        "planned_hours": planned,
        "total_hours": state.earned_hours + planned,
        "required_total_hours": float(ctx.program["total_hours_min"]),
        "upper_level_hours": upper,
        "required_upper_level_hours": float(ctx.program["upper_level_hours_min"]),
        "atu_hours": state.atu_hours + planned - transfer,
        "exam_hours": state.exam_hours,
        "transfer_hours": transfer
        + float(
            sum(c.hours for c in state.credits.values() if c.source == "transfer" and c.counts_toward_degree)
        ),
    }


# ----------------------------------------------------------------------------- warnings


def _policy_source(ctx: PlanContext, key: str) -> SourceLink | None:
    sources = ctx.policies.sources_for(key)
    first = next((s for s in sources if s.url), None)
    return SourceLink(title=first.title, url=first.url) if first else None


def policy_warnings(ctx: PlanContext, outcome: Outcome, terms: list[PlannedTerm]) -> list[Warning]:
    policies = ctx.policies
    out: list[Warning] = []
    tot = totals(ctx, outcome)
    if tot["atu_hours"] < policies.residency_min_hours:
        out.append(
            Warning(
                id="residency",
                severity="error",
                category="policy",
                message=f"Only {tot['atu_hours']:g} hours at ATU; residency needs "
                f"{policies.residency_min_hours}.",
                source=_policy_source(ctx, "residency_min_hours"),
                policy_key="residency_min_hours",
            )
        )
    upper_major = sum(
        i.hours
        for i in outcome.build.items
        if i.upper and i.in_major and not outcome.result.placements[i.id].transfer
    ) + sum(
        c.hours
        for c in outcome.state.credits.values()
        if c.counts_toward_degree and c.at_atu and c.level >= 3000
    )
    if upper_major < policies.residency_upper_major_hours:
        out.append(
            Warning(
                id="residency-upper",
                severity="warning",
                category="policy",
                message=f"Residency also needs {policies.residency_upper_major_hours} upper-"
                "division hours in the major at ATU; confirm with your advisor.",
                source=_policy_source(ctx, "residency_upper_major_hours"),
                policy_key="residency_upper_major_hours",
            )
        )
    if tot["upper_level_hours"] + 0.01 < tot["required_upper_level_hours"]:
        out.append(
            Warning(
                id="upper-level",
                severity="error",
                category="policy",
                message=f"Plan reaches {tot['upper_level_hours']:g} upper-level hours; "
                f"{tot['required_upper_level_hours']:g} required.",
                source=SourceLink(title="Degree map", url=ctx.program["sources"][0]["url"]),
            )
        )
    if tot["total_hours"] + 0.01 < tot["required_total_hours"]:
        out.append(
            Warning(
                id="total-hours",
                severity="error",
                category="policy",
                message=f"Plan totals {tot['total_hours']:g} hours; "
                f"{tot['required_total_hours']:g} required.",
                source=_policy_source(ctx, "total_hours_min"),
                policy_key="total_hours_min",
            )
        )
    cap = policies.exam_credit_cap_hours
    if outcome.state.exam_hours > cap:
        out.append(
            Warning(
                id="exam-cap",
                severity="error",
                category="policy",
                message=f"{outcome.state.exam_hours:g} hours of exam credit exceed the "
                f"{cap}-hour cap. The cap itself is disputed between ATU pages "
                "(30 hours vs. 50% of the degree); confirm with the registrar.",
                source=_policy_source(ctx, "exam_credit_cap_hours"),
                policy_key="exam_credit_cap_hours",
            )
        )
    elif outcome.state.exam_hours > 0:
        out.append(
            Warning(
                id="exam-cap-info",
                severity="info",
                category="policy",
                message=f"{outcome.state.exam_hours:g} of {cap} allowed exam-credit hours used "
                "(stricter of two conflicting ATU rules; confirm with the registrar).",
                source=_policy_source(ctx, "exam_credit_cap_hours"),
                policy_key="exam_credit_cap_hours",
            )
        )
    if outcome.state.exam_hours > 0:
        out.append(
            Warning(
                id="exam-gpa",
                severity="info",
                category="policy",
                message="Exam credit doesn't count toward GPA, so it can't help you keep a scholarship.",
                source=_policy_source(ctx, "exam_credit_gpa"),
                policy_key="exam_credit_gpa",
            )
        )
    for term in terms:
        if term.overload:
            key = (
                "overload_review_threshold"
                if term.hours > policies.overload_review_threshold
                else "overload_gpa_min"
            )
            out.append(
                Warning(
                    id=f"overload-{term.id}",
                    severity="warning",
                    category="policy",
                    message=f"{term.label}: {term.hours:g} hours is an overload. Needs a dean "
                    f"petition and a {policies.overload_gpa_min:.2f} GPA the term before"
                    + (
                        " plus Academic Affairs review."
                        if term.hours > policies.overload_review_threshold
                        else "."
                    ),
                    source=_policy_source(ctx, key),
                    policy_key=key,
                )
            )
    if ctx.plan_from == ctx.first_term and (ctx.levers.overload or ctx.levers.aggressive_overload):
        out.append(
            Warning(
                id="first-term",
                severity="info",
                category="policy",
                message=f"No overload in your first ATU term ({ctx.first_term.label}): there's "
                "no prior-term GPA yet.",
                source=_policy_source(ctx, "first_term_no_overload"),
                policy_key="first_term_no_overload",
            )
        )
    thresholds = policies.standing_thresholds
    standing_names = {"SO": "sophomore", "JR": "junior", "SR": "senior"}
    for item in outcome.build.items:
        if item.standing and item.code:
            when = outcome.result.slots[outcome.result.placements[item.id].term_index].term
            out.append(
                Warning(
                    id=f"standing-{item.id}",
                    severity="info",
                    category="policy",
                    message=f"{item.label} requires {standing_names.get(item.standing, item.standing)} "
                    f"standing ({thresholds.get(item.standing, 0)}+ earned hours); "
                    f"scheduled {when.label}.",
                    source=_policy_source(ctx, "standing_thresholds"),
                    policy_key="standing_thresholds",
                )
            )
    gpa = ctx.profile.preferences.last_term_gpa
    if gpa is not None and gpa < 2.0:
        out.append(
            Warning(
                id="probation",
                severity="warning",
                category="policy",
                message=f"If you're on academic probation, loads over "
                f"{policies.probation_advisor_threshold} hours need advisor approval.",
                source=_policy_source(ctx, "probation_advisor_threshold"),
                policy_key="probation_advisor_threshold",
            )
        )
    return out


def data_warnings(ctx: PlanContext, outcome: Outcome, terms: list[PlannedTerm]) -> list[Warning]:
    program = ctx.program
    map_link = SourceLink(title=f"{program['catalog_year']} degree map", url=program["sources"][0]["url"])
    out: list[Warning] = []
    if program["trust_tier"] == "needs_review":
        failed = [r["check"] for r in program.get("validation", []) if not r["passed"]]
        out.append(
            Warning(
                id="needs-review",
                severity="warning",
                category="data",
                message=f"This program's data needs review ({', '.join(failed)}). Treat the "
                "plan as a rough sketch and check it against the degree map.",
                source=map_link,
            )
        )
    for gate in program.get("admission_gates", []):
        out.append(
            Warning(
                id=f"gate-{abs(hash(gate)) % 10000}",
                severity="warning",
                category="data",
                message=f"Admission gate: {gate}. Shortcut can't compress an admission "
                "cycle; check application deadlines.",
                source=map_link,
            )
        )
    for term in terms:
        for course in term.courses:
            if course.low_confidence:
                out.append(
                    Warning(
                        id=f"offering-{course.item_id}-{term.id}",
                        severity="warning",
                        category="data",
                        message=f"{course.label} in {term.label}: offering not confirmed "
                        f"({course.offering_note or course.offering_confidence}).",
                        source=SourceLink(title="ATU class schedule", url=SCHEDULE_URL),
                    )
                )
            if course.offering_confidence == "conflicting":
                out.append(
                    Warning(
                        id=f"conflict-{course.item_id}",
                        severity="info",
                        category="data",
                        message=f"{course.label}: {course.offering_note}.",
                        source=map_link,
                    )
                )
    placed_codes = {i.code for i in outcome.build.items if i.code}
    for code in sorted(placed_codes):
        record = ctx.dataset.courses.get(code)
        if record and record.get("parse_confidence") in ("low", "medium") and record.get("prerequisites"):
            out.append(
                Warning(
                    id=f"prereq-{code}",
                    severity="info",
                    category="data",
                    message=f"{code} prerequisite read with {record['parse_confidence']} "
                    f'confidence: "{record.get("prereq_raw") or "see catalog"}".',
                    source=SourceLink(title="ATU course catalog (Banner)", url=BANNER_URL),
                )
            )
    for message in outcome.build.warnings:
        out.append(
            Warning(
                id=f"build-{zlib.crc32(message.encode()) % 100000}",
                severity="info",
                category="plan",
                message=message,
                source=map_link,
            )
        )
    if not ctx.levers.summer:
        for term in terms:
            atu = [c.code or c.label for c in term.courses if term.season == "SU" and not c.transfer]
            if atu:
                out.append(
                    Warning(
                        id=f"summer-only-{term.id}",
                        severity="info",
                        category="plan",
                        message=f"{', '.join(atu)} {'is' if len(atu) == 1 else 'are'} offered only in "
                        f"summer, so the plan includes {term.label} even with summer terms off.",
                        source=map_link,
                    )
                )
    return out


def base_assumptions(ctx: PlanContext, outcome: Outcome) -> list[str]:
    policies = ctx.policies
    items: list[str] = [
        "Every planned course is passed on the first try with at least the grade it requires.",
        "Summer sub-sessions are merged into one planning term; 8-week sessions aren't modeled.",
        f"Summer is capped at {policies.summer_max_load} hours and winter at "
        f"{policies.winter_max_courses} course (≤{policies.winter_max_hours} hours) for planning.",
        "Class standing counts exam and transfer hours (confirm with the registrar).",
        "Elective slots can be filled by any qualifying course; approved electives need advisor sign-off.",
        "Upper-level elective slots are placed after junior standing (60 hours), since most 3000-4000 "
        "courses require it.",
    ]
    if ctx.mode == "conservative":
        items.append(
            "Conservative mode: summer/winter courses are scheduled only when the catalog, "
            "the degree map, or the last three years of schedules support it."
        )
    else:
        items.append(
            "Optimistic mode: courses with unknown summer/winter availability may be scheduled "
            "(each one is flagged)."
        )
    if ctx.profile.in_progress:
        items.append("In-progress courses are assumed passed with a C.")
    if ctx.profile.math_act is None:
        items.append("No math ACT entered: math placement is assumed. Enter it for an accurate plan.")
    uses_tests = any(_has_nonmath_test(i.prereq) for i in outcome.build.items)
    if uses_tests:
        items.append("English/reading placement is assumed (only the math ACT is collected).")
    if ctx.levers.transfer_summer:
        items.append(
            "Transfer courses assume an ACTS-equivalent section is available at another "
            "Arkansas public college that summer."
        )
    if outcome.planned_exams:
        items.append("Planned exams are assumed passed at the qualifying score before the plan starts.")
    return items


def _has_nonmath_test(tree: dict[str, Any] | None) -> bool:
    if not tree:
        return False
    if tree["type"] == "test":
        return not is_math_test(tree)
    return any(_has_nonmath_test(t) for t in tree.get("items", []))


def explain_infeasible(ctx: PlanContext, outcome: Outcome) -> str:
    result = outcome.result
    by_id = {i.id: i for i in outcome.build.items}
    if result.unplaceable:
        names = []
        for item_id in result.unplaceable[:5]:
            item = by_id.get(item_id)
            if item is None:
                continue
            seasons = item.pattern(ctx.mode) or "no season with confirmed availability"
            names.append(f"{item.label} (offered: {seasons})")
        return (
            "No valid plan: these can't be placed within 16 semesters under the current settings: "
            + "; ".join(names)
            + ". Try Optimistic mode or check the course data."
        )
    if result.status == "unknown":
        return "The solver hit its time limit before finding a plan. Try fewer levers."
    return (
        "No valid plan within 16 regular semesters under the current settings (prerequisite, "
        "offering, and hour-cap constraints conflict)."
    )


__all__ = [
    "DetailedPlan",
    "Outcome",
    "PlanContext",
    "make_context",
    "months_between",
    "plan",
    "plan_detailed",
    "run_solve",
]
