import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import type { ProgramListItem } from '../api/types'
import { defaultProfile } from '../state/profile'
import { StepMajor } from './Setup'

const base = { name: '', listed_title: 'Accounting', degree: '', degree_abbr: 'BBA', college: 'Business', trust_tier: 'auto_imported' as const, issues: [] }
const programs: ProgramListItem[] = [
  { ...base, id: 'accounting-2026-27', catalog_year: '2026-27', major_key: 'accounting', successors: [] },
  { ...base, id: 'accounting-2025-26', catalog_year: '2025-26', major_key: 'accounting', successors: ['accounting-2026-27'] },
]
const profile = { ...defaultProfile('accounting-2026-27'), first_term: '2026FA' }

describe('Setup: major and catalog year', () => {
  it('switches to the map for the year the student started', async () => {
    const update = vi.fn()
    render(<StepMajor profile={profile} programs={programs} detail={null} update={update} />)
    await userEvent.selectOptions(screen.getByLabelText('First term at ATU'), '2025FA')
    expect(update).toHaveBeenCalledWith({ first_term: '2025FA', program_id: 'accounting-2025-26' })
  })

  it('lets the student choose another catalog year of the same major', async () => {
    const update = vi.fn()
    render(<StepMajor profile={profile} programs={programs} detail={null} update={update} />)
    expect(screen.getByText(/Your catalog year is on your Degree Works audit/)).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Catalog year'), 'accounting-2025-26')
    expect(update).toHaveBeenCalledWith({ program_id: 'accounting-2025-26' })
  })
})
