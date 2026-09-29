import type { CompletedCourse, Grade, ProgramListItem, StudentProfile } from '../api/types'
import { versionsOf } from '../catalogYear'
import { defaultProfile } from '../state/profile'
import type { AuditCourse, AuditImport } from './types'

export interface ProfileImport {
  profile: StudentProfile
  programMatch: 'exact' | 'year_missing' | 'none'
  /** Plain-language assumptions, shown on the review screen. */
  notes: string[]
}

const LETTERS = new Set(['A', 'B', 'C', 'D', 'F', 'P'])
const SEASON_ORDER: Record<string, number> = { FA: 0, WI: 1, SP: 2, SU: 3 }

/** Sort key for "2025FA": academic year, then fall < winter < spring < summer. */
function termKey(term: string): number {
  const year = Number(term.slice(0, 4))
  const season = term.slice(4)
  const academicYear = season === 'FA' || season === 'WI' ? year : year - 1
  return academicYear * 10 + (SEASON_ORDER[season] ?? 0)
}

/** The next fall or spring after `term` (winter and summer lead into the next regular term). */
export function nextTermAfter(term: string): string {
  const year = Number(term.slice(0, 4))
  const season = term.slice(4)
  if (season === 'FA') return `${year + 1}SP`
  if (season === 'WI') return `${year + 1}SP`
  return `${year}FA`
}

function nextTermAfterDate(today: Date): string {
  const month = today.getMonth() // 0-based
  const year = today.getFullYear()
  return month <= 4 ? `${year}FA` : `${year + 1}SP`
}

const normalize = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

/** "BS Computer Science" -> the programs whose degree abbreviation and title match. */
function matchMajor(degree: string, programs: ProgramListItem[]): ProgramListItem[] {
  const [abbr = '', ...rest] = degree.trim().split(/\s+/)
  const title = normalize(rest.join(' '))
  return programs.filter(
    (p) => normalize(p.listed_title) === title && (!p.degree_abbr || p.degree_abbr.toUpperCase() === abbr.toUpperCase()),
  )
}

function toCompleted(course: AuditCourse): CompletedCourse | null {
  const base = { code: course.code, hours: course.credits }
  if (course.examProgram || course.grade === 'CE') {
    return { ...base, grade: 'P', source: 'exam', ...(course.exam ? { exam: course.exam } : {}) }
  }
  if (/^T[A-DFPR]$/.test(course.grade) || course.transfer) {
    const letter = course.grade.slice(1)
    return { ...base, grade: (LETTERS.has(letter) ? letter : 'P') as Grade, source: 'transfer' }
  }
  if (course.grade === 'CR') return { ...base, grade: 'P', source: 'atu' }
  if (LETTERS.has(course.grade)) return { ...base, grade: course.grade as Grade, source: 'atu' }
  return null // W, NC, IP: no credit (in-progress is handled separately)
}

export function auditToProfile(audit: AuditImport, programs: ProgramListItem[], today = new Date()): ProfileImport {
  const notes: string[] = []
  const candidates = audit.degree ? matchMajor(audit.degree, programs) : []
  let programId = ''
  let programMatch: ProfileImport['programMatch'] = 'none'
  const first = candidates[0]
  if (first) {
    const exact = candidates.find((p) => p.catalog_year === audit.catalogYear)
    const newest = versionsOf(programs, first.id)[0] ?? first
    programId = (exact ?? newest).id
    programMatch = exact ? 'exact' : 'year_missing'
    if (!exact) {
      notes.push(
        `Your audit's catalog year is ${audit.catalogYear ?? 'not shown'}, which Shortcut doesn't have a map for. It used the ${newest.catalog_year} map instead; check the requirements with your advisor.`,
      )
    }
  } else {
    notes.push(`Shortcut couldn't match “${audit.degree ?? 'your degree'}” to one of its majors. Pick your major below.`)
  }

  const inProgress = audit.courses.filter((c) => c.grade === 'IP')
  const completed = audit.courses.map(toCompleted).filter((c): c is CompletedCourse => c !== null)
  const atuTerms = audit.courses
    .filter((c) => c.term && !c.examProgram && !c.transfer && c.grade !== 'CE' && !c.grade.startsWith('T'))
    .map((c) => c.term as string)
    .sort((a, b) => termKey(a) - termKey(b))
  const latestIp = inProgress
    .map((c) => c.term)
    .filter((t): t is string => Boolean(t))
    .sort((a, b) => termKey(b) - termKey(a))[0]
  const latestAtu = atuTerms[atuTerms.length - 1]
  const planFrom = latestIp ? nextTermAfter(latestIp) : latestAtu ? nextTermAfter(latestAtu) : nextTermAfterDate(today)
  const firstTerm = atuTerms[0] ?? planFrom

  const highGpa = audit.gpa !== null && audit.gpa >= 3.25
  if (audit.gpa !== null) {
    notes.push(
      highGpa
        ? `Overall GPA ${audit.gpa.toFixed(2)} on your audit, so Shortcut assumes you'll keep 3.25+ for overload eligibility.`
        : `Overall GPA ${audit.gpa.toFixed(2)} on your audit, below the 3.25 overloads need.`,
    )
  }
  const withdrawn = audit.courses.filter((c) => c.grade === 'W').length
  if (withdrawn === 1) notes.push('1 withdrawn course (W) carries no credit and was left out.')
  if (withdrawn > 1) notes.push(`${String(withdrawn)} withdrawn courses (W) carry no credit and were left out.`)

  const profile: StudentProfile = {
    ...defaultProfile(programId),
    first_term: firstTerm,
    plan_from: planFrom === firstTerm ? null : planFrom,
    completed,
    in_progress: inProgress.map((c) => c.code),
  }
  profile.preferences = { ...profile.preferences, expect_high_gpa: highGpa }
  return { profile, programMatch, notes }
}
