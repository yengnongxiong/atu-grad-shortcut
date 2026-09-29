"""API routes (PRD §11). Planner endpoints are sync so FastAPI runs them in a worker thread."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from shortcut.data.loader import Dataset, load_dataset
from shortcut.planner.exams import delay_impact, exam_opportunities
from shortcut.planner.profile import offered_ok
from shortcut.planner.service import plan
from shortcut.planner.whatif import WhatIfError, run_whatif
from shortcut.schemas.api import (
    CourseBrief,
    ExamRow,
    ExamsResponse,
    ExamTable,
    HealthResponse,
    MetaResponse,
    Persona,
    PersonasResponse,
    PolicyOut,
    ProgramDetail,
    ProgramListItem,
    RequirementOut,
    ValidationOut,
)
from shortcut.schemas.plan import (
    DelayRequest,
    DelayResponse,
    ExamOpportunitiesResponse,
    PlanRequest,
    PlanResponse,
    SourceLink,
    WhatIfRequest,
    WhatIfResponse,
)

DISCLAIMER = (
    "Not affiliated with Arkansas Tech University. Not official advising. "
    "Confirm your plan with your advisor."
)

ASSUMPTIONS = [
    "Every planned course is passed on the first try with at least the grade it requires.",
    "In-progress courses are assumed passed with a C.",
    "Summer sub-sessions are merged into one planning term; 8-week sessions aren't modeled.",
    "Summer and winter caps are planning assumptions (see policies).",
    "Class standing counts exam and transfer hours.",
    "Placement: only the math ACT is collected; other placement tests are assumed met.",
    "Fall/spring availability defaults to 'assumed' unless the catalog, a degree map, or three years "
    "of schedules say otherwise.",
    "Summer/winter availability comes from the catalog or the Fall 2023–Spring 2027 public schedule; "
    "a course that ran before may not run again.",
    "Upper-level elective slots are placed after junior standing.",
    "Transfer courses must be ACTS-equivalent and lower-level; availability elsewhere is assumed.",
    "Planned exams are assumed passed at the qualifying score before the plan starts.",
    "The exam-credit cap uses the stricter of two conflicting ATU rules (30 hours).",
]

router = APIRouter(prefix="/api")


def _dataset() -> Dataset:
    return load_dataset()


DS = Annotated[Dataset, Depends(_dataset)]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/meta", response_model=MetaResponse)
def meta(ds: DS) -> MetaResponse:
    m = ds.meta
    policies = ds.policies
    rules: list[PolicyOut] = []
    for key, rule in policies.raw["rules"].items():
        rules.append(
            PolicyOut(
                key=key,
                label=rule["label"],
                value=rule["value"],
                unit=rule["unit"],
                confidence=rule["confidence"],
                note=rule.get("note", ""),
                sources=[SourceLink(title=s.title, url=s.url) for s in policies.sources_for(key)],
            )
        )
    return MetaResponse(
        generated_at=m["generated_at"],
        pipeline_mode=m["pipeline_mode"],
        newest_catalog_year=m["newest_catalog_year"],
        catalog_status=m["catalog_status"],
        banner_status=m["banner_status"],
        discovered_maps=m["discovered_maps"],
        bachelor_programs=m["bachelor_programs"],
        tier_counts=m["tier_counts"],
        course_count=m["course_count"],
        sources=[SourceLink(**s) for s in m["sources"]],
        policies=rules,
        assumptions=ASSUMPTIONS,
        exam_programs={t["program"]: t["status"] for t in ds.exams.values()},
        disclaimer=DISCLAIMER,
    )


@router.get("/programs", response_model=list[ProgramListItem])
def programs(ds: DS) -> list[ProgramListItem]:
    items = [
        ProgramListItem(
            id=p["id"],
            name=p["name"],
            listed_title=p.get("listed_title", p["name"]),
            degree=p["degree"],
            degree_abbr=p.get("degree_abbr", ""),
            college=p.get("college", ""),
            catalog_year=p["catalog_year"],
            trust_tier=p["trust_tier"],
            issues=[f"{v['check']}: {v['detail']}" for v in p.get("validation", []) if not v["passed"]],
        )
        for p in ds.programs.values()
    ]
    order = {"cross_checked": 0, "auto_imported": 1, "needs_review": 2}
    return sorted(items, key=lambda p: (order.get(p.trust_tier, 3), p.listed_title))


@router.get("/programs/{program_id}", response_model=ProgramDetail)
def program_detail(program_id: str, ds: DS) -> ProgramDetail:
    program = ds.programs.get(program_id)
    if program is None:
        raise HTTPException(status_code=404, detail=f"unknown program {program_id!r}")
    codes: set[str] = set()
    requirements: list[RequirementOut] = []
    for req in program["requirements"]:
        options = req.get("options", []) if req["kind"] == "course" else []
        bucket = req.get("bucket") or {}
        codes.update(c for o in options for c in o)
        codes.update(bucket.get("codes", []))
        requirements.append(
            RequirementOut(
                id=req["id"],
                kind=req["kind"],
                label=req["label"],
                hours=req.get("hours"),
                min_grade=req.get("min_grade"),
                map_semester=req["map_semester"],
                options=options,
                bucket_codes=bucket.get("codes", []),
                rule=bucket.get("rule"),
                confidence=req.get("confidence", "high"),
                warnings=req.get("warnings", []),
            )
        )
    return ProgramDetail(
        id=program["id"],
        name=program["name"],
        listed_title=program.get("listed_title", program["name"]),
        degree=program["degree"],
        degree_abbr=program.get("degree_abbr", ""),
        college=program.get("college", ""),
        catalog_year=program["catalog_year"],
        trust_tier=program["trust_tier"],
        total_hours_min=float(program["total_hours_min"]),
        upper_level_hours_min=float(program["upper_level_hours_min"]),
        gpa_min=float(program.get("gpa_min") or 2.0),
        requirements=requirements,
        map_schedule=program["map_schedule"],
        courses={c: _brief(ds, c) for c in sorted(codes) if c in ds.courses},
        validation=[ValidationOut(**v) for v in program.get("validation", [])],
        cross_check=program.get("cross_check"),
        admission_gates=program.get("admission_gates", []),
        notes=program.get("notes", []),
        sources=[SourceLink(**s) for s in program.get("sources", [])],
    )


def _brief(ds: Dataset, code: str) -> CourseBrief:
    course = ds.courses[code]
    letters = {"FA": "F", "WI": "W", "SP": "S", "SU": "Su"}
    pattern = "/".join(
        letters[s] for s in ("FA", "WI", "SP", "SU") if offered_ok(course["offered"][s], "conservative")
    )
    return CourseBrief(
        code=code,
        title=course["title"],
        hours=course.get("hours"),
        level=course["level"],
        offered=pattern,
        prereq_raw=course.get("prereq_raw", ""),
        standing=course.get("standing"),
    )


@router.get("/exams", response_model=ExamsResponse)
def exams(ds: DS) -> ExamsResponse:
    tables: list[ExamTable] = []
    for name in ("clep", "ap", "ib"):
        table: dict[str, Any] | None = ds.exams.get(name)
        if table is None:
            continue
        source = table.get("source") or {}
        tables.append(
            ExamTable(
                program=table["program"],
                status=table["status"],
                note=table.get("note", ""),
                source=SourceLink(title=str(source.get("title", "")), url=str(source.get("url", ""))),
                equivalencies=[
                    ExamRow(
                        id=r["id"],
                        program=r["program"],
                        exam=r["exam"],
                        min_score=float(r["min_score"]),
                        awards=r["awards"],
                        award_hours=r.get("award_hours", []),
                        generic_credit=r.get("generic_credit"),
                    )
                    for r in table.get("equivalencies", [])
                ],
            )
        )
    return ExamsResponse(tables=tables)


@router.get("/personas", response_model=PersonasResponse)
def personas(ds: DS) -> PersonasResponse:
    out = [
        Persona(
            id=p["id"],
            name=p["name"],
            tagline=p["tagline"],
            story=p.get("story", ""),
            sample_data=bool(p.get("sample_data")),
            request=PlanRequest.model_validate(p["request"]),
        )
        for p in ds.personas.values()
        if p["request"]["profile"]["program_id"] in ds.programs
    ]
    return PersonasResponse(personas=sorted(out, key=lambda p: p.id))


def _check_program(ds: Dataset, program_id: str) -> None:
    if program_id not in ds.programs:
        raise HTTPException(status_code=404, detail=f"unknown program {program_id!r}")


@router.post("/plan", response_model=PlanResponse)
def create_plan(request: PlanRequest, ds: DS) -> PlanResponse:
    _check_program(ds, request.profile.program_id)
    try:
        return plan(ds, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plan/whatif", response_model=WhatIfResponse)
def create_whatif(request: WhatIfRequest, ds: DS) -> WhatIfResponse:
    _check_program(ds, request.plan.profile.program_id)
    if request.event.program_id:
        _check_program(ds, request.event.program_id)
    try:
        return run_whatif(ds, request)
    except (WhatIfError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plan/exam-opportunities", response_model=ExamOpportunitiesResponse)
def create_exam_opportunities(request: PlanRequest, ds: DS) -> ExamOpportunitiesResponse:
    _check_program(ds, request.profile.program_id)
    try:
        return exam_opportunities(ds, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plan/delay-impact", response_model=DelayResponse)
def create_delay_impact(request: DelayRequest, ds: DS) -> DelayResponse:
    _check_program(ds, request.plan.profile.program_id)
    try:
        return delay_impact(ds, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
