import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { api } from '../api/client'
import type { ProgramListItem } from '../api/types'
import { defaultLevers, defaultProfile } from '../state/profile'
import { samplePlan } from '../test/fixtures'
import { WhatIfPanel } from './WhatIfPanel'

const base = { name: '', degree: '', degree_abbr: 'BS', college: 'STEM', trust_tier: 'auto_imported' as const, issues: [] }
const programs: ProgramListItem[] = [
  { ...base, id: 'computer-science-2025-26', listed_title: 'Computer Science', catalog_year: '2025-26', major_key: 'computer-science',
    successors: ['computer-science-software-dev-2026-27'] },
  { ...base, id: 'computer-science-software-dev-2026-27', listed_title: 'Computer Science Software Development', catalog_year: '2026-27',
    major_key: 'computer-science-software-dev', successors: [] },
]

it('re-plans the same credits against a newer catalog of the major', async () => {
  const whatIf = vi.spyOn(api, 'whatIf').mockResolvedValue({
    event: { type: 'change_major', program_id: 'computer-science-software-dev-2026-27' },
    before: null, after: null, terms_later: 0, changed_terms: [], explanation: 'Same date.', plan: samplePlan(),
  } as unknown as Awaited<ReturnType<typeof api.whatIf>>)
  const request = { profile: defaultProfile('computer-science-2025-26'), levers: defaultLevers() }
  render(<WhatIfPanel plan={samplePlan()} request={request} programs={programs} />)
  await userEvent.click(screen.getByLabelText('I switch to a newer catalog'))
  expect(screen.getByText(/any later catalog/)).toBeInTheDocument()
  await userEvent.selectOptions(screen.getByLabelText('Newer catalog'), 'computer-science-software-dev-2026-27')
  await userEvent.click(screen.getByRole('button', { name: 'Run what-if' }))
  expect(whatIf).toHaveBeenCalledWith(request, { type: 'change_major', program_id: 'computer-science-software-dev-2026-27' })
})
