"""Pydantic models for the non-plan API endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shortcut.schemas.plan import PlanRequest, SourceLink


class HealthResponse(BaseModel):
    status: str


class PolicyOut(BaseModel):
    key: str
    label: str
    value: Any
    unit: str
    confidence: str
    note: str
    sources: list[SourceLink]


class MetaResponse(BaseModel):
    generated_at: str
    pipeline_mode: str
    newest_catalog_year: str
    catalog_status: str
    banner_status: str
    discovered_maps: int
    bachelor_programs: int
    tier_counts: dict[str, int]
    course_count: int
    sources: list[SourceLink]
    policies: list[PolicyOut]
    assumptions: list[str]
    exam_programs: dict[str, str]
    disclaimer: str


class ProgramListItem(BaseModel):
    id: str
    name: str
    listed_title: str
    degree: str
    degree_abbr: str
    college: str
    catalog_year: str
    trust_tier: str
    issues: list[str]


class RequirementOut(BaseModel):
    id: str
    kind: str
    label: str
    hours: float | None
    min_grade: str | None
    map_semester: int
    options: list[list[str]] = Field(default_factory=list)
    bucket_codes: list[str] = Field(default_factory=list)
    rule: dict[str, Any] | None = None
    confidence: str
    warnings: list[str] = Field(default_factory=list)


class CourseBrief(BaseModel):
    code: str
    title: str
    hours: float | None
    level: int
    offered: str
    prereq_raw: str
    standing: str | None


class ValidationOut(BaseModel):
    check: str
    passed: bool
    severity: str
    detail: str


class ProgramDetail(BaseModel):
    id: str
    name: str
    listed_title: str
    degree: str
    degree_abbr: str
    college: str
    catalog_year: str
    trust_tier: str
    total_hours_min: float
    upper_level_hours_min: float
    gpa_min: float
    requirements: list[RequirementOut]
    map_schedule: list[dict[str, Any]]
    courses: dict[str, CourseBrief]
    validation: list[ValidationOut]
    cross_check: dict[str, Any] | None
    admission_gates: list[str]
    notes: list[str]
    sources: list[SourceLink]


class ExamRow(BaseModel):
    id: str
    program: str
    exam: str
    min_score: float
    awards: list[list[str]]
    award_hours: list[float | None]
    generic_credit: str | None = None  # e.g. "3 hours General Education Humanities" (no course named)


class ExamTable(BaseModel):
    program: str
    status: str
    note: str = ""
    source: SourceLink
    equivalencies: list[ExamRow]


class ExamsResponse(BaseModel):
    tables: list[ExamTable]


class Persona(BaseModel):
    id: str
    name: str
    tagline: str
    story: str
    sample_data: bool
    request: PlanRequest


class PersonasResponse(BaseModel):
    personas: list[Persona]
