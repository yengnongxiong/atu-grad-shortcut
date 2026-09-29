import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import type { ProgramListItem } from '../api/types'
import { ProgramPicker } from './ProgramPicker'

const base = { name: '', listed_title: 'Accounting', degree: '', degree_abbr: 'BBA', college: 'Business', trust_tier: 'auto_imported' as const, issues: [] }
const programs: ProgramListItem[] = [
  { ...base, id: 'accounting-2026-27', catalog_year: '2026-27', major_key: 'accounting', successors: [] },
  { ...base, id: 'accounting-2025-26', catalog_year: '2025-26', major_key: 'accounting', successors: ['accounting-2026-27'] },
]

describe('ProgramPicker', () => {
  it('lists a major once and picks the preferred catalog year', async () => {
    const onSelect = vi.fn()
    render(<ProgramPicker programs={programs} preferredYear="2025-26" onSelect={onSelect} />)
    await userEvent.type(screen.getByRole('combobox'), 'accounting')
    expect(screen.getAllByRole('option')).toHaveLength(1)
    expect(screen.getByRole('option')).toHaveTextContent('2025-26 catalog · also 2026-27')
    await userEvent.click(screen.getByRole('option'))
    expect(onSelect).toHaveBeenCalledWith(programs[1])
  })

  it('defaults to the newest catalog year', async () => {
    const onSelect = vi.fn()
    render(<ProgramPicker programs={programs} onSelect={onSelect} />)
    await userEvent.type(screen.getByRole('combobox'), 'accounting')
    await userEvent.click(screen.getByRole('option'))
    expect(onSelect).toHaveBeenCalledWith(programs[0])
  })
})
