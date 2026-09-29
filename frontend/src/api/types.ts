// Mirrors backend/shortcut/schemas/{plan,api}.py. Keep in sync.

export type Grade = 'A' | 'B' | 'C' | 'D' | 'F' | 'P' | 'W'
export type Mode = 'conservative' | 'optimistic'
export type Confidence = 'documented' | 'derived' | 'assumed' | 'unknown' | 'conflicting'
export type Season = 'FA' | 'WI' | 'SP' | 'SU'
export type TrustTier = 'cross_checked' | 'auto_imported' | 'needs_review'

export interface CompletedCourse {
  code: string
  grade: Grade
  /** exam = credit by exam already on the record (a Degree Works "CE" row) */
  source: 'atu' | 'transfer' | 'exam'
  /** Hours from the student's record; omitted means the catalog's hours. */
  hours?: number | null
  /** The exam that awarded the credit, for display only. */
  exam?: string | null
}

export interface ExamScore {
  program: 'CLEP' | 'AP' | 'IB'
  exam: string
  score: number
}

export interface Preferences {
  preferred_hours: number | null
  last_term_gpa: number | null
  expect_high_gpa: boolean
  mode: Mode
}

export interface Levers {
  heavier_terms: boolean
  summer: boolean
  winter: boolean
  overload: boolean
  aggressive_overload: boolean
  transfer_summer: boolean
  planned_exams: string[]
}

export type LeverId = Exclude<keyof Levers, 'planned_exams'> | 'planned_exams'

export interface StudentProfile {
  program_id: string
  first_term: string
  plan_from: string | null
  completed: CompletedCourse[]
  in_progress: string[]
  exams: ExamScore[]
  math_act: number | null
  preferences: Preferences
}

export interface PlanRequest {
  profile: StudentProfile
  levers: Levers
  include_attribution?: boolean
}

export interface SourceLink {
  title: string
  url: string
}

export interface TermRef {
  id: string
  label: string
  date_label: string
}

export interface PlannedCourse {
  item_id: string
  code: string | null
  label: string
  title: string
  hours: number
  kind: 'course' | 'bucket' | 'elective' | 'filler' | 'added_prereq'
  requirement_id: string | null
  transfer: boolean
  critical: boolean
  slack: number | null
  offering_confidence: Confidence
  offering_note: string
  low_confidence: boolean
  options: string[]
  min_grade: string | null
}

export interface PlannedTerm {
  id: string
  label: string
  season: Season
  hours: number
  cap: number
  courses: PlannedCourse[]
  workload_low: number
  workload_high: number
  overload: boolean
  approval: string | null
}

export interface CreditedCourse {
  code: string
  title: string
  hours: number
  source: string
  grade: string | null
  requirement_id: string | null
  counts_toward: string
}

export interface LeverResult {
  id: LeverId
  label: string
  enabled: boolean
  available: boolean
  terms_saved: number | null
  months_saved: number | null
  cost: 'none' | 'extra tuition' | 'exam fee' | 'tuition elsewhere'
  approval: 'none' | 'advisor' | 'dean petition' | 'dean petition + Academic Affairs'
  workload: string
  note: string
  policy_key?: string | null
}

export interface PlanWarning {
  id: string
  severity: 'info' | 'warning' | 'error'
  category: 'policy' | 'data' | 'plan'
  message: string
  source: SourceLink | null
  policy_key: string | null
}

export interface GraphNode {
  id: string
  label: string
  title: string
  term: string
  term_index: number
  slack: number | null
  critical: boolean
  pattern: string
  hours: number
}

export interface GraphEdge {
  source: string
  target: string
  kind: 'prereq' | 'coreq'
  critical: boolean
}

export interface Baseline {
  graduation: TermRef | null
  note: string
}

export interface PlanStats {
  solve_ms: number
  solves: number
  status: string
  timed_out: boolean
}

export interface ProgramSummary {
  id: string
  name: string
  degree: string
  degree_abbr: string
  college: string
  catalog_year: string
  trust_tier: TrustTier
  total_hours_min: number
  upper_level_hours_min: number
}

export interface PlanResponse {
  program: ProgramSummary
  feasible: boolean
  infeasible_reason: string | null
  graduation: TermRef | null
  degree_map: Baseline
  standard_pace: Baseline
  terms_sooner_than_map: number | null
  terms_sooner_than_standard: number | null
  months_sooner_than_standard: number | null
  pace_note?: string | null
  terms: PlannedTerm[]
  credited: CreditedCourse[]
  levers: LeverResult[]
  critical_path: string[]
  critical_chain?: string[]
  graph_nodes: GraphNode[]
  graph_edges: GraphEdge[]
  warnings: PlanWarning[]
  assumptions: string[]
  totals: Record<string, number>
  stats: PlanStats
}

export interface WhatIfEvent {
  type: 'fail' | 'drop' | 'skip' | 'change_major'
  code?: string | null
  term?: string | null
  hours?: number | null
  program_id?: string | null
}

export interface TermChange {
  term: string
  label: string
  before: string[]
  after: string[]
}

export interface WhatIfResponse {
  event: WhatIfEvent
  explanation: string
  before: TermRef | null
  after: TermRef | null
  terms_later: number | null
  changed_terms: TermChange[]
  plan: PlanResponse
}

export interface ExamOpportunity {
  id: string
  program: string
  exam: string
  min_score: number
  awards: string[]
  requirements_satisfied: string[]
  hours_saved: number
  terms_saved: number | null
  months_saved: number | null
  exceeds_cap: boolean
  cap_note: string
  source: SourceLink
}

export interface ExamOpportunitiesResponse {
  opportunities: ExamOpportunity[]
  exam_hours_used: number
  exam_cap_hours: number
  unavailable_programs: string[]
  note: string
}

export interface DelayResponse {
  item_id: string
  label: string
  from_term: TermRef | null
  to_term: TermRef | null
  before: TermRef | null
  after: TermRef | null
  terms_later: number | null
  explanation: string
}

// ---------------------------------------------------------------- non-plan endpoints

export interface PolicyOut {
  key: string
  label: string
  value: unknown
  unit: string
  confidence: Confidence
  note: string
  sources: SourceLink[]
}

export interface CatalogSnapshot {
  title: string
  url: string
  catalog_edition: string
  captured_at: string
}

export interface MetaResponse {
  generated_at: string
  pipeline_mode: string
  newest_catalog_year: string
  catalog_years?: string[]
  catalog_status: string
  banner_status: string
  discovered_maps: number
  bachelor_programs: number
  tier_counts: Record<string, number>
  tier_counts_by_year?: Record<string, Record<string, number>>
  course_count: number
  sources: SourceLink[]
  catalog_snapshots?: CatalogSnapshot[]
  policies: PolicyOut[]
  assumptions: string[]
  exam_programs: Record<string, string>
  disclaimer: string
}

export interface ProgramListItem {
  id: string
  name: string
  listed_title: string
  degree: string
  degree_abbr: string
  college: string
  catalog_year: string
  trust_tier: TrustTier
  issues: string[]
  /** The same major across catalog years */
  major_key?: string
  /** This major in newer catalogs */
  successors?: string[]
}

export interface RequirementOut {
  id: string
  kind: 'course' | 'bucket'
  label: string
  hours: number | null
  min_grade: string | null
  map_semester: number
  options: string[][]
  bucket_codes: string[]
  rule: Record<string, unknown> | null
  confidence: string
  warnings: string[]
}

export interface CourseBrief {
  code: string
  title: string
  hours: number | null
  level: number
  offered: string
  prereq_raw: string
  standing: string | null
}

export interface ValidationOut {
  check: string
  passed: boolean
  severity: string
  detail: string
}

export interface ProgramDetail {
  id: string
  name: string
  listed_title: string
  degree: string
  degree_abbr: string
  college: string
  catalog_year: string
  trust_tier: TrustTier
  total_hours_min: number
  upper_level_hours_min: number
  gpa_min: number
  requirements: RequirementOut[]
  map_schedule: { semester: number; stated_total: string; items: { requirement_id: string; label: string; hours: number | null }[] }[]
  courses: Record<string, CourseBrief>
  validation: ValidationOut[]
  cross_check: Record<string, unknown> | null
  admission_gates: string[]
  notes: string[]
  sources: SourceLink[]
}

export interface ExamRow {
  id: string
  program: string
  exam: string
  min_score: number
  awards: string[][]
  award_hours: (number | null)[]
  /** Credit that names no course, e.g. "3 hours General Education Humanities". */
  generic_credit?: string | null
}

export interface ExamTable {
  program: string
  status: string
  note: string
  source: SourceLink
  equivalencies: ExamRow[]
}

export interface ExamsResponse {
  tables: ExamTable[]
}

export interface Persona {
  id: string
  name: string
  tagline: string
  story: string
  sample_data: boolean
  request: PlanRequest
}

export interface PersonasResponse {
  personas: Persona[]
}
