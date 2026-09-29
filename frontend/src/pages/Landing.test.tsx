import { render, screen } from '@testing-library/react'
import type { ProgramListItem } from '../api/types'
import { Landing } from './Landing'

const base = { name: '', degree: '', degree_abbr: 'BBA', college: 'Business', issues: [] }
const programs: ProgramListItem[] = [
  { ...base, id: 'accounting-2026-27', listed_title: 'Accounting', catalog_year: '2026-27', major_key: 'accounting', successors: [], trust_tier: 'cross_checked' },
  { ...base, id: 'accounting-2025-26', listed_title: 'Accounting', catalog_year: '2025-26', major_key: 'accounting', successors: ['accounting-2026-27'], trust_tier: 'needs_review' },
  { ...base, id: 'finance-2026-27', listed_title: 'Finance', catalog_year: '2026-27', major_key: 'finance', successors: [], trust_tier: 'auto_imported' },
]

describe('Landing', () => {
  it('counts majors, not catalog-year versions of them', () => {
    render(<Landing programs={programs} personas={[]} loading={false} onPickProgram={() => {}} onPersona={() => {}} />)
    expect(screen.getByText('Majors').nextElementSibling).toHaveTextContent('2')
  })

  it('names every kind of exam credit Shortcut reads', () => {
    render(<Landing programs={programs} personas={[]} loading={false} onPickProgram={() => {}} onPersona={() => {}} />)
    expect(screen.getByText(/AP, IB, and CLEP credit/)).toBeInTheDocument()
  })
})
