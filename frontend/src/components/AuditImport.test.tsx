import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import type { ProgramListItem } from '../api/types'
import { SAMPLE_AUDIT } from '../degreeworks/fixtures/sample-audit'
import { readPdfLines } from '../degreeworks/pdfLines'
import { AuditImport } from './AuditImport'

vi.mock('../degreeworks/pdfLines', () => ({ readPdfLines: vi.fn(async () => SAMPLE_AUDIT) }))
vi.mock('../api/client', () => ({
  api: {
    meta: () =>
      Promise.resolve({
        policies: [{ key: 'overload_gpa_min', label: '', value: 3.25, unit: 'GPA', confidence: 'documented', note: '', sources: [] }],
      }),
  },
}))

const base = { name: '', degree: 'Bachelor of Science', degree_abbr: 'BS', college: 'STEM', trust_tier: 'cross_checked' as const, issues: [] }
const cs: ProgramListItem = {
  ...base,
  id: 'computer-science-2025-26',
  listed_title: 'Computer Science',
  catalog_year: '2025-26',
  major_key: 'computer-science',
  successors: [],
}
const programs: ProgramListItem[] = [cs]
const pdf = () => new File(['%PDF-1.7'], 'audit.pdf', { type: 'application/pdf' })

describe('AuditImport', () => {
  it('says the file stays on the device', () => {
    render(<AuditImport programs={programs} onApply={() => {}} />)
    expect(screen.getByText(/never uploaded/)).toBeInTheDocument()
  })

  it('shows what it read before applying it', async () => {
    render(<AuditImport programs={programs} onApply={() => {}} />)
    await userEvent.upload(screen.getByLabelText(/Degree Works audit \(PDF\)/), pdf())
    expect(await screen.findByText('Computer Science · 2025-26 catalog')).toBeInTheDocument()
    expect(screen.getByText('7 completed at ATU')).toBeInTheDocument()
    expect(screen.getByText('5 by exam')).toBeInTheDocument()
    expect(screen.getByText('1 transfer')).toBeInTheDocument()
    expect(screen.getByText('2 in progress')).toBeInTheDocument()
    expect(screen.getByText(/withdrawn/)).toBeInTheDocument()
  })

  it('counts in words that agree with the number', async () => {
    vi.mocked(readPdfLines).mockResolvedValueOnce([...SAMPLE_AUDIT, 'ZZZZ 1234 smudged row Fall Term'])
    render(<AuditImport programs={programs} onApply={() => {}} />)
    await userEvent.upload(screen.getByLabelText(/Degree Works audit \(PDF\)/), pdf())
    expect(await screen.findByText('1 line Shortcut couldn’t read')).toBeInTheDocument()
    expect(screen.getByText('40 credits applied, per Degree Works')).toBeInTheDocument()
  })

  it('lets the student pick a catalog year when the audit names one Shortcut lacks', async () => {
    vi.mocked(readPdfLines).mockResolvedValueOnce(SAMPLE_AUDIT.map((line) => line.replace('Catalog year: 2025-2026', 'Catalog year: 2019-2020')))
    const newer: ProgramListItem = { ...cs, id: 'computer-science-2026-27', catalog_year: '2026-27' }
    const onApply = vi.fn()
    render(<AuditImport programs={[cs, newer]} onApply={onApply} />)
    await userEvent.upload(screen.getByLabelText(/Degree Works audit \(PDF\)/), pdf())
    const year = await screen.findByRole('combobox', { name: 'Catalog year' })
    expect(year).toHaveValue('computer-science-2026-27')
    await userEvent.selectOptions(year, 'computer-science-2025-26')
    await userEvent.click(screen.getByRole('button', { name: 'Use this record' }))
    expect(onApply.mock.calls[0]?.[0].profile.program_id).toBe('computer-science-2025-26')
  })

  it('applies the record as a plan request and hands back the audit', async () => {
    const onApply = vi.fn()
    render(<AuditImport programs={programs} onApply={onApply} />)
    await userEvent.upload(screen.getByLabelText(/Degree Works audit \(PDF\)/), pdf())
    await userEvent.click(await screen.findByRole('button', { name: 'Use this record' }))
    const [request, audit] = onApply.mock.calls[0] as [{ profile: { program_id: string; in_progress: string[] } }, { catalogYear: string }]
    expect(request.profile.program_id).toBe('computer-science-2025-26')
    expect(request.profile.in_progress).toEqual(['COMS 2163', 'COMS 2213'])
    expect(audit.catalogYear).toBe('2025-26')
  })

  it('asks for the major when the audit names one Shortcut does not have', async () => {
    render(<AuditImport programs={[{ ...cs, listed_title: 'History', id: 'history-2025-26' }]} onApply={() => {}} />)
    await userEvent.upload(screen.getByLabelText(/Degree Works audit \(PDF\)/), pdf())
    expect(await screen.findByText(/couldn’t match/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Use this record' })).toBeDisabled()
  })

  it('rejects a file that is not a Degree Works audit', async () => {
    const { readPdfLines } = await import('../degreeworks/pdfLines')
    vi.mocked(readPdfLines).mockResolvedValueOnce(['Hello', 'world'])
    render(<AuditImport programs={programs} onApply={() => {}} />)
    await userEvent.upload(screen.getByLabelText(/Degree Works audit \(PDF\)/), pdf())
    expect(await screen.findByRole('alert')).toHaveTextContent(/doesn’t look like a Degree Works audit/)
  })
})
