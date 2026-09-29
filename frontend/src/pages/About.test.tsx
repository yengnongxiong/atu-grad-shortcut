import { render, screen, within } from '@testing-library/react'
import { vi } from 'vitest'
import type { MetaResponse } from '../api/types'
import { About } from './About'

const meta = vi.hoisted(
  (): MetaResponse => ({
    generated_at: '2026-09-29T16:40:41+00:00',
    pipeline_mode: 'offline',
    newest_catalog_year: '2026-27',
    catalog_years: ['2025-26', '2026-27'],
    catalog_status: 'not probed',
    banner_status: 'loaded committed snapshots',
    discovered_maps: 161,
    bachelor_programs: 145,
    tier_counts: { cross_checked: 5, auto_imported: 110, needs_review: 30, excluded: 16 },
    tier_counts_by_year: {
      '2025-26': { cross_checked: 1, auto_imported: 54, needs_review: 17, excluded: 8 },
      '2026-27': { cross_checked: 4, auto_imported: 56, needs_review: 13, excluded: 8 },
    },
    course_count: 911,
    sources: [],
    catalog_snapshots: [
      {
        title: 'Advanced Placement (AP)',
        url: 'https://catalog.atu.edu/undergraduate/institutional-credit/ap/',
        catalog_edition: '2026-2027',
        captured_at: '2026-09-29',
      },
    ],
    policies: [],
    assumptions: [],
    exam_programs: { AP: 'available' },
    disclaimer: 'Not affiliated with Arkansas Tech University.',
  }),
)

vi.mock('../api/client', () => ({ api: { meta: () => Promise.resolve(meta) } }))

describe('About the data', () => {
  it('shows trust tiers for each catalog year', async () => {
    render(<About programs={[]} />)
    const table = await screen.findByRole('table', { name: 'Programs by catalog year and trust tier' })
    const row = within(table).getByRole('row', { name: /2025-26/ })
    expect(within(row).getAllByRole('cell').map((c) => c.textContent)).toEqual(['1', '54', '17', '8'])
  })

  it('says when each catalog page was saved', async () => {
    render(<About programs={[]} />)
    const link = await screen.findByRole('link', { name: 'Advanced Placement (AP)' })
    expect(link.closest('li')).toHaveTextContent('2026-2027 catalog, saved 2026-09-29')
    expect(screen.queryByText(/not probed/)).not.toBeInTheDocument()
  })
})
