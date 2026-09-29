import type { CompletedCourse, ExamScore, Grade, Levers, PlanRequest, StudentProfile } from '../api/types'

export const STORAGE_KEY = 'shortcut.plan.v1'
export const SHARE_PARAM = 's'

export const defaultLevers = (): Levers => ({
  heavier_terms: false,
  summer: false,
  winter: false,
  overload: false,
  aggressive_overload: false,
  transfer_summer: false,
  planned_exams: [],
})

export const defaultProfile = (programId = ''): StudentProfile => ({
  program_id: programId,
  first_term: '2026FA',
  plan_from: null,
  completed: [],
  in_progress: [],
  exams: [],
  math_act: null,
  preferences: {
    preferred_hours: null,
    last_term_gpa: null,
    expect_high_gpa: false,
    mode: 'conservative',
  },
})

export const defaultRequest = (programId = ''): PlanRequest => ({
  profile: defaultProfile(programId),
  levers: defaultLevers(),
})

function toBase64Url(text: string): string {
  const bytes = new TextEncoder().encode(text)
  let binary = ''
  bytes.forEach((b) => {
    binary += String.fromCharCode(b)
  })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

function fromBase64Url(value: string): string {
  const padded = value.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((value.length + 3) % 4)
  const binary = atob(padded)
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0))
  return new TextDecoder().decode(bytes)
}

export function encodeRequest(request: PlanRequest): string {
  return toBase64Url(JSON.stringify({ p: request.profile, l: request.levers }))
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

const GRADE_VALUES: readonly Grade[] = ['A', 'B', 'C', 'D', 'F', 'P', 'W']
const SOURCE_VALUES: readonly CompletedCourse['source'][] = ['atu', 'transfer', 'exam']
const EXAM_PROGRAMS: readonly ExamScore['program'][] = ['CLEP', 'AP', 'IB']

function completedRow(raw: unknown): CompletedCourse | null {
  if (!isRecord(raw) || typeof raw.code !== 'string' || !GRADE_VALUES.includes(raw.grade as Grade)) return null
  const row: CompletedCourse = {
    code: raw.code,
    grade: raw.grade as Grade,
    source: SOURCE_VALUES.includes(raw.source as CompletedCourse['source']) ? (raw.source as CompletedCourse['source']) : 'atu',
  }
  if (typeof raw.hours === 'number' && raw.hours >= 0) row.hours = raw.hours
  if (typeof raw.exam === 'string') row.exam = raw.exam
  return row
}

function examRow(raw: unknown): ExamScore | null {
  if (!isRecord(raw) || typeof raw.exam !== 'string' || typeof raw.score !== 'number') return null
  if (!EXAM_PROGRAMS.includes(raw.program as ExamScore['program'])) return null
  return { program: raw.program as ExamScore['program'], exam: raw.exam, score: raw.score }
}

const rows = <T,>(raw: unknown, parse: (value: unknown) => T | null): T[] =>
  Array.isArray(raw) ? raw.map(parse).filter((row): row is T => row !== null) : []

/** Parse untrusted JSON (URL or storage) into a request, falling back to defaults per field. */
export function normalizeRequest(raw: unknown): PlanRequest | null {
  if (!isRecord(raw)) return null
  const profileRaw = isRecord(raw.p) ? raw.p : isRecord(raw.profile) ? raw.profile : null
  const leversRaw = isRecord(raw.l) ? raw.l : isRecord(raw.levers) ? raw.levers : {}
  if (!profileRaw || typeof profileRaw.program_id !== 'string') return null
  const base = defaultProfile(profileRaw.program_id)
  const prefs = isRecord(profileRaw.preferences) ? profileRaw.preferences : {}
  const profile: StudentProfile = {
    ...base,
    first_term: typeof profileRaw.first_term === 'string' ? profileRaw.first_term : base.first_term,
    plan_from: typeof profileRaw.plan_from === 'string' ? profileRaw.plan_from : null,
    completed: rows(profileRaw.completed, completedRow),
    in_progress: rows(profileRaw.in_progress, (v) => (typeof v === 'string' ? v : null)),
    exams: rows(profileRaw.exams, examRow),
    math_act: typeof profileRaw.math_act === 'number' ? profileRaw.math_act : null,
    preferences: {
      preferred_hours: typeof prefs.preferred_hours === 'number' ? prefs.preferred_hours : null,
      last_term_gpa: typeof prefs.last_term_gpa === 'number' ? prefs.last_term_gpa : null,
      expect_high_gpa: prefs.expect_high_gpa === true,
      mode: prefs.mode === 'optimistic' ? 'optimistic' : 'conservative',
    },
  }
  const defaults = defaultLevers()
  const levers: Levers = {
    heavier_terms: leversRaw.heavier_terms === true,
    summer: leversRaw.summer === true,
    winter: leversRaw.winter === true,
    overload: leversRaw.overload === true,
    aggressive_overload: leversRaw.aggressive_overload === true,
    transfer_summer: leversRaw.transfer_summer === true,
    planned_exams: Array.isArray(leversRaw.planned_exams)
      ? (leversRaw.planned_exams as string[]).filter((x) => typeof x === 'string')
      : defaults.planned_exams,
  }
  return { profile, levers }
}

export function decodeRequest(value: string): PlanRequest | null {
  try {
    return normalizeRequest(JSON.parse(fromBase64Url(value)))
  } catch {
    return null
  }
}

export function shareUrl(request: PlanRequest, origin = window.location.origin): string {
  return `${origin}/plan?${SHARE_PARAM}=${encodeRequest(request)}`
}

export function saveRequest(request: PlanRequest): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ p: request.profile, l: request.levers }))
  } catch {
    // storage can be unavailable (private mode); the share link still works
  }
}

export function loadRequest(): PlanRequest | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeRequest(JSON.parse(raw)) : null
  } catch {
    return null
  }
}

/** Term helpers mirroring backend/shortcut/planner/terms.py. */
export const SEASON_NAMES: Record<string, string> = { FA: 'Fall', WI: 'Winter', SP: 'Spring', SU: 'Summer' }

export function termLabel(id: string): string {
  const match = /^(\d{4})(FA|WI|SP|SU)$/.exec(id)
  if (!match) return id
  const year = Number(match[1])
  const season = match[2] ?? 'FA'
  if (season === 'WI') return `Winter ${year}–${String(year + 1).slice(2)}`
  return `${SEASON_NAMES[season] ?? season} ${year}`
}

export function termOptions(fromYear = 2024, toYear = 2030): { id: string; label: string }[] {
  const out: { id: string; label: string }[] = []
  for (let year = fromYear; year <= toYear; year += 1) {
    out.push({ id: `${year}SP`, label: termLabel(`${year}SP`) })
    out.push({ id: `${year}SU`, label: termLabel(`${year}SU`) })
    out.push({ id: `${year}FA`, label: termLabel(`${year}FA`) })
  }
  return out
}
