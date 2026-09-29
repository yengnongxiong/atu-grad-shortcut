import type { ProgramListItem } from '../api/types'
import { SAMPLE_AUDIT } from './fixtures/sample-audit'
import { parseAudit } from './parse'
import { auditToProfile, nextTermAfter } from './toProfile'

const base = { name: '', degree: 'Bachelor of Science', degree_abbr: 'BS', college: 'STEM', trust_tier: 'cross_checked' as const, issues: [] }
const PROGRAMS: ProgramListItem[] = [
  { ...base, id: 'computer-science-2025-26', listed_title: 'Computer Science', catalog_year: '2025-26', major_key: 'computer-science', successors: [] },
  { ...base, id: 'computer-science-ai-2026-27', listed_title: 'Computer ScienceAI', catalog_year: '2026-27', major_key: 'computer-science-ai', successors: [] },
  { ...base, id: 'accounting-2026-27', listed_title: 'Accounting', degree_abbr: 'BBA', catalog_year: '2026-27', major_key: 'accounting', successors: [] },
  { ...base, id: 'accounting-2025-26', listed_title: 'Accounting', degree_abbr: 'BBA', catalog_year: '2025-26', major_key: 'accounting', successors: [] },
]
const audit = parseAudit(SAMPLE_AUDIT)
const today = new Date('2026-09-29')

describe('auditToProfile', () => {
  const { profile, programMatch, notes } = auditToProfile(audit, PROGRAMS, today)
  const row = (code: string) => profile.completed.find((c) => c.code === code)

  it('matches the major and the catalog year', () => {
    expect(programMatch).toBe('exact')
    expect(profile.program_id).toBe('computer-science-2025-26')
  })

  it('turns posted exam credit into exam-sourced courses with their hours', () => {
    expect(row('ENGL 1013')).toEqual({ code: 'ENGL 1013', grade: 'P', source: 'exam', hours: 3, exam: 'AP10 - ENGLISH LITERATURE/COMP' })
    expect(row('COMS 1411')).toMatchObject({ source: 'exam', hours: 1 })
  })

  it('keeps ATU grades and transfer credit', () => {
    expect(row('TECH 1001')).toEqual({ code: 'TECH 1001', grade: 'B', source: 'atu', hours: 1 })
    expect(row('ENGL 2003')).toEqual({ code: 'ENGL 2003', grade: 'B', source: 'transfer', hours: 3 })
  })

  it('puts in-progress courses in progress and skips withdrawals', () => {
    expect(profile.in_progress).toEqual(['COMS 2163', 'COMS 2213'])
    expect(row('MATH 2703')).toBeUndefined()
    expect(notes).toContain('1 withdrawn course (W) carries no credit and was left out.')
  })

  it('infers the first ATU term and plans from the term after the in-progress one', () => {
    expect(profile.first_term).toBe('2025FA')
    expect(profile.plan_from).toBe('2027SP')
  })

  it('reads a 3.25+ GPA as eligible for overloads, and says so', () => {
    expect(profile.preferences.expect_high_gpa).toBe(true)
    expect(notes.join(' ')).toMatch(/3\.50/)
  })

  it('falls back to the newest catalog year Shortcut has, and says so', () => {
    const r = auditToProfile({ ...audit, degree: 'BBA Accounting', catalogYear: '2019-20' }, PROGRAMS, today)
    expect(r.programMatch).toBe('year_missing')
    expect(r.profile.program_id).toBe('accounting-2026-27')
    expect(r.notes.join(' ')).toMatch(/2019-20/)
  })

  it('reports an unknown major instead of guessing', () => {
    const r = auditToProfile({ ...audit, degree: 'BS Underwater Basketry' }, PROGRAMS, today)
    expect(r.programMatch).toBe('none')
    expect(r.profile.program_id).toBe('')
  })
})

describe('nextTermAfter', () => {
  it.each([
    ['2026FA', '2027SP'],
    ['2027SP', '2027FA'],
    ['2027SU', '2027FA'],
    ['2026WI', '2027SP'],
  ])('%s → %s', (term, next) => expect(nextTermAfter(term)).toBe(next))
})
