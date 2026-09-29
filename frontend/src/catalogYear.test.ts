import { catalogYearFor, onePerMajor, versionFor, versionsOf } from './catalogYear'

it.each([
  ['2025FA', '2025-26'],
  ['2026SP', '2025-26'],
  ['2026SU', '2025-26'],
  ['2026WI', '2026-27'],
  ['2026FA', '2026-27'],
  ['2099FA', '2099-00'],
])('a student who starts in %s follows the %s catalog', (term, year) => expect(catalogYearFor(term)).toBe(year))

describe('versions of a major', () => {
  const base = { name: '', listed_title: 'Accounting', degree: '', degree_abbr: 'BBA', college: '', trust_tier: 'auto_imported' as const, issues: [] }
  const programs = [
    { ...base, id: 'accounting-2025-26', catalog_year: '2025-26', major_key: 'accounting', successors: ['accounting-2026-27'] },
    { ...base, id: 'accounting-2026-27', catalog_year: '2026-27', major_key: 'accounting', successors: [] },
    { ...base, id: 'history-2026-27', listed_title: 'History', catalog_year: '2026-27', major_key: 'history', successors: [] },
  ]

  it('lists every catalog year of a major, newest first', () => {
    expect(versionsOf(programs, 'accounting-2025-26').map((p) => p.catalog_year)).toEqual(['2026-27', '2025-26'])
  })

  it('picks the version for a catalog year, or keeps the program when that year has none', () => {
    expect(versionFor(programs, 'accounting-2026-27', '2025-26')).toBe('accounting-2025-26')
    expect(versionFor(programs, 'history-2026-27', '2025-26')).toBe('history-2026-27')
  })

  it('shows one entry per major, choosing the preferred year when it exists', () => {
    expect(onePerMajor(programs, '2025-26').map((p) => p.id)).toEqual(['accounting-2025-26', 'history-2026-27'])
    expect(onePerMajor(programs).map((p) => p.id)).toEqual(['accounting-2026-27', 'history-2026-27'])
  })
})
