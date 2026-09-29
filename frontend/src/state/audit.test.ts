import { defaultProfile } from './profile'
import { auditFor, recordKey } from './audit'
import type { AuditImport } from '../degreeworks/types'

const audit: AuditImport = {
  degree: 'BS Computer Science', catalogYear: '2025-26', gpa: 3.5, creditsRequired: 120, creditsApplied: 4,
  courses: [], stillNeeded: [], unrecognized: [],
}
const imported = {
  ...defaultProfile('computer-science-2025-26'),
  completed: [{ code: 'ENGL 1013', grade: 'P' as const, source: 'exam' as const, hours: 3 }],
  in_progress: ['COMS 2163'],
}
const stored = { programId: imported.program_id, recordKey: recordKey(imported), audit }

describe('which plan an imported audit belongs to', () => {
  it('belongs to the imported record', () => {
    expect(auditFor(stored, imported)).toBe(audit)
  })

  it('does not belong to another profile in the same program (e.g. a demo persona)', () => {
    expect(auditFor(stored, defaultProfile('computer-science-2025-26'))).toBeNull()
  })

  it('does not belong to the same courses planned against another program', () => {
    expect(auditFor(stored, { ...imported, program_id: 'computer-science-ai-2026-27' })).toBeNull()
  })

  it('ignores the order courses are listed in', () => {
    expect(recordKey({ ...imported, in_progress: ['B', 'A'] })).toBe(recordKey({ ...imported, in_progress: ['A', 'B'] }))
  })
})
