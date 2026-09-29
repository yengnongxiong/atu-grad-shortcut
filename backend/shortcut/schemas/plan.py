"""Pydantic models for plan requests and responses (mirrored in frontend/src/api/types.ts)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Grade = Literal["A", "B", "C", "D", "F", "P", "W"]
Mode = Literal["conservative", "optimistic"]
Confidence = Literal["documented", "derived", "assumed", "unknown", "conflicting"]


class CompletedCourse(BaseModel):
    code: str
    grade: Grade = "C"
    # exam = credit by exam already on the record (e.g. a Degree Works "CE" row)
    source: Literal["atu", "transfer", "exam"] = "atu"
    hours: float | None = Field(default=None, ge=0, le=12)  # None: use the catalog's hours
    exam: str | None = None  # the exam that awarded it, for display only

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return " ".join(value.upper().replace("-", " ").split())


class ExamScore(BaseModel):
    program: Literal["CLEP", "AP", "IB"] = "CLEP"
    exam: str
    score: float = Field(ge=0)


class Preferences(BaseModel):
    preferred_hours: int | None = Field(default=None, ge=3, le=24)
    last_term_gpa: float | None = Field(default=None, ge=0, le=4)
    expect_high_gpa: bool = False
    mode: Mode = "conservative"


class Levers(BaseModel):
    heavier_terms: bool = False
    summer: bool = False
    winter: bool = False
    overload: bool = False
    aggressive_overload: bool = False
    transfer_summer: bool = False
    planned_exams: list[str] = Field(default_factory=list)


class StudentProfile(BaseModel):
    program_id: str
    first_term: str = "2026FA"
    plan_from: str | None = None
    completed: list[CompletedCourse] = Field(default_factory=list)
    in_progress: list[str] = Field(default_factory=list)
    exams: list[ExamScore] = Field(default_factory=list)
    math_act: int | None = Field(default=None, ge=1, le=36)
    preferences: Preferences = Field(default_factory=Preferences)


class PlanRequest(BaseModel):
    profile: StudentProfile
    levers: Levers = Field(default_factory=Levers)
    include_attribution: bool = True


# ----------------------------------------------------------------------------- response


class SourceLink(BaseModel):
    title: str
    url: str


class TermRef(BaseModel):
    id: str
    label: str
    date_label: str


class PlannedCourse(BaseModel):
    item_id: str
    code: str | None
    label: str
    title: str
    hours: float
    kind: Literal["course", "bucket", "elective", "filler", "added_prereq"]
    requirement_id: str | None
    transfer: bool = False
    critical: bool = False
    slack: float | None = None
    offering_confidence: Confidence
    offering_note: str = ""
    low_confidence: bool = False
    options: list[str] = Field(default_factory=list)
    min_grade: str | None = None


class PlannedTerm(BaseModel):
    id: str
    label: str
    season: Literal["FA", "WI", "SP", "SU"]
    hours: float
    cap: float
    courses: list[PlannedCourse]
    workload_low: float
    workload_high: float
    overload: bool = False
    approval: str | None = None


class CreditedCourse(BaseModel):
    code: str
    title: str
    hours: float
    source: str
    grade: str | None
    requirement_id: str | None
    counts_toward: str


class LeverResult(BaseModel):
    id: str
    label: str
    enabled: bool
    available: bool = True
    terms_saved: float | None = None
    months_saved: int | None = None
    cost: Literal["none", "extra tuition", "exam fee", "tuition elsewhere"]
    approval: Literal["none", "advisor", "dean petition", "dean petition + Academic Affairs"]
    workload: str
    note: str = ""
    policy_key: str | None = None  # the policies.json rule behind the lever's numbers


class Warning(BaseModel):
    id: str
    severity: Literal["info", "warning", "error"]
    category: Literal["policy", "data", "plan"]
    message: str
    source: SourceLink | None = None
    policy_key: str | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    title: str
    term: str
    term_index: int
    slack: float | None
    critical: bool
    pattern: str
    hours: float


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: Literal["prereq", "coreq"]
    critical: bool


class Baseline(BaseModel):
    graduation: TermRef | None
    note: str


class PlanStats(BaseModel):
    solve_ms: int
    solves: int
    status: str
    timed_out: bool = False


class ProgramSummary(BaseModel):
    id: str
    name: str
    degree: str
    degree_abbr: str
    college: str
    catalog_year: str
    trust_tier: str
    total_hours_min: float
    upper_level_hours_min: float


class PlanResponse(BaseModel):
    program: ProgramSummary
    feasible: bool
    infeasible_reason: str | None = None
    graduation: TermRef | None
    degree_map: Baseline
    standard_pace: Baseline
    terms_sooner_than_map: float | None
    terms_sooner_than_standard: float | None
    months_sooner_than_standard: int | None
    pace_note: str | None = None  # why the date can't move, when no lever helps
    terms: list[PlannedTerm]
    credited: list[CreditedCourse]
    levers: list[LeverResult]
    critical_path: list[str]
    critical_chain: list[str] = []  # longest prerequisite chain through critical items, in order
    graph_nodes: list[GraphNode]
    graph_edges: list[GraphEdge]
    warnings: list[Warning]
    assumptions: list[str]
    totals: dict[str, float]
    stats: PlanStats


class WhatIfEvent(BaseModel):
    type: Literal["fail", "drop", "skip", "change_major"]
    code: str | None = None
    term: str | None = None
    hours: int | None = Field(default=None, ge=0, le=24)
    program_id: str | None = None


class WhatIfRequest(BaseModel):
    plan: PlanRequest
    event: WhatIfEvent


class TermChange(BaseModel):
    term: str
    label: str
    before: list[str]
    after: list[str]


class WhatIfResponse(BaseModel):
    event: WhatIfEvent
    explanation: str
    before: TermRef | None
    after: TermRef | None
    terms_later: float | None
    changed_terms: list[TermChange]
    plan: PlanResponse


class ExamOpportunity(BaseModel):
    id: str
    program: str
    exam: str
    min_score: float
    awards: list[str]
    requirements_satisfied: list[str]
    hours_saved: float
    terms_saved: float | None
    months_saved: int | None
    exceeds_cap: bool
    cap_note: str = ""
    source: SourceLink


class ExamOpportunitiesResponse(BaseModel):
    opportunities: list[ExamOpportunity]
    exam_hours_used: float
    exam_cap_hours: float
    unavailable_programs: list[str]
    note: str


class DelayRequest(BaseModel):
    plan: PlanRequest
    item_id: str


class DelayResponse(BaseModel):
    item_id: str
    label: str
    from_term: TermRef | None
    to_term: TermRef | None
    before: TermRef | None
    after: TermRef | None
    terms_later: float | None
    explanation: str
