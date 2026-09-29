import { SAMPLE_AUDIT } from './fixtures/sample-audit'
import { parseAudit } from './parse'

const audit = parseAudit(SAMPLE_AUDIT)
const byCode = (code: string) => {
  const found = audit.courses.find((c) => c.code === code)
  if (!found) throw new Error(`${code} not parsed`)
  return found
}

describe('parseAudit', () => {
  it('reads the degree, catalog year, GPA, and credit totals', () => {
    expect(audit.degree).toBe('BS Computer Science')
    expect(audit.catalogYear).toBe('2025-26')
    expect(audit.gpa).toBe(3.5)
    expect([audit.creditsRequired, audit.creditsApplied]).toEqual([120, 70])
  })

  it('reads a completed ATU course', () => {
    expect(byCode('TECH 1001')).toMatchObject({ grade: 'B', credits: 1, term: '2025FA', exam: null, transfer: false, section: 'requirement' })
  })

  it('reads posted AP credit whose term wrapped onto the next line', () => {
    expect(byCode('ENGL 1013')).toMatchObject({ grade: 'CE', credits: 3, term: '2024SP', examProgram: 'AP', exam: 'AP10 - ENGLISH LITERATURE/COMP' })
  })

  it('attaches "Satisfied by" across a page break', () => {
    expect(byCode('POLS 2003')).toMatchObject({ examProgram: 'CLEP', exam: 'CL01 - AMERICAN GOVERNMENT' })
  })

  it('joins a title that wrapped together with the year', () => {
    expect(byCode('COMS 2703')).toMatchObject({ title: 'COMP HARDWARE & ARCHITECTURE', grade: 'B', term: '2026SP' })
    expect(byCode('COMS 1011')).toMatchObject({ title: 'PROGRAMMING FOUNDATIONS I LAB', grade: 'P', term: '2025FA' })
  })

  it('reads in-progress rows once, with parenthesized credits', () => {
    expect(byCode('COMS 2163')).toMatchObject({ grade: 'IP', credits: 3, term: '2026FA', section: 'requirement' })
    expect(audit.courses.filter((c) => c.code === 'COMS 2163')).toHaveLength(1)
  })

  it('keeps unapplied credit from the Not Used section', () => {
    expect(byCode('COMS 1411')).toMatchObject({ section: 'not_used', credits: 1, grade: 'CE', examProgram: 'AP' })
  })

  it('marks transfer credit', () => {
    expect(byCode('ENGL 2003')).toMatchObject({ transfer: true, grade: 'TB', term: '2025SU', examProgram: null })
  })

  it('reads a withdrawal as a row, not credit', () => {
    expect(byCode('MATH 2703').grade).toBe('W')
  })

  it('collects still-needed courses, carrying the subject across "or" lists and lines', () => {
    expect(audit.stillNeeded).toContainEqual({ label: 'Algorithm Design and Analysis', codes: ['COMS 3213'], anyUpperLevel: false })
    expect(audit.stillNeeded).toContainEqual({
      label: 'Social Sciences',
      codes: ['ECON 2003', 'ECON 2013', 'HIST 1503', 'HIST 1513', 'PSY 2003'],
      anyUpperLevel: false,
    })
  })

  it('reads a "choose from" block as one requirement with every option', () => {
    const science = audit.stillNeeded.find((s) => s.label === 'SCIENCE WITH LAB COURSE')
    expect(science?.codes).toEqual([
      'PHSC 1013', 'PHSC 1053', 'CHEM 1113', 'PHSC 1021', 'PHSC 1051', 'CHEM 1111',
      'BIOL 1004', 'BIOL 1014', 'BIOL 1114', 'GEOL 1014', 'GEOL 2024', 'PHYS 2014',
    ])
  })

  it('reads a 3000–4000 level elective rule', () => {
    expect(audit.stillNeeded).toContainEqual({ label: 'Approved electives', codes: [], anyUpperLevel: true })
  })

  it('skips narrative still-needed lines that name no course', () => {
    expect(audit.stillNeeded.map((s) => s.label)).not.toContain('General Education Requirements')
  })

  it('never exposes the student name or ID', () => {
    expect(JSON.stringify(audit)).not.toMatch(/Sample, Student|T00000000/)
  })

  it('returns an empty import for text that is not an audit', () => {
    expect(parseAudit(['Hello', 'world'])).toMatchObject({ degree: null, catalogYear: null, courses: [], stillNeeded: [] })
  })
})
