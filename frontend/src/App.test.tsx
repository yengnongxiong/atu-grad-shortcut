import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import type { Persona, PlanResponse, ProgramListItem } from './api/types'
import { samplePlan } from './test/fixtures'

const programs: ProgramListItem[] = [
  {
    id: 'computer-science-2025-26',
    name: 'Computer Science',
    listed_title: 'Computer Science',
    degree: 'Bachelor of Science',
    degree_abbr: 'BS',
    college: 'Science/Technology/Engr/Math',
    catalog_year: '2025-26',
    trust_tier: 'cross_checked',
    issues: [],
  },
  {
    id: 'music-2026-27',
    name: 'Music',
    listed_title: 'Music',
    degree: 'Bachelor of Arts',
    degree_abbr: 'BA',
    college: 'Arts and Humanities',
    catalog_year: '2026-27',
    trust_tier: 'needs_review',
    issues: ['semester_hours_match: semester 1'],
  },
]

const persona: Persona = {
  id: 'p1',
  name: 'Starting from scratch',
  tagline: 'Incoming CS freshman',
  story: '',
  sample_data: false,
  request: {
    profile: {
      program_id: 'computer-science-2025-26',
      first_term: '2026FA',
      plan_from: null,
      completed: [],
      in_progress: [],
      exams: [],
      math_act: 27,
      preferences: { preferred_hours: 16, last_term_gpa: null, expect_high_gpa: true, mode: 'conservative' },
    },
    levers: {
      heavier_terms: false,
      summer: false,
      winter: false,
      overload: false,
      aggressive_overload: false,
      transfer_summer: false,
      planned_exams: [],
    },
  },
}

function mockApi(plan: PlanResponse = samplePlan()) {
  globalThis.fetch = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const body = url.endsWith('/api/programs')
      ? programs
      : url.endsWith('/api/personas')
        ? { personas: [persona] }
        : url.endsWith('/api/plan')
          ? plan
          : {}
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  }) as unknown as typeof fetch
}

describe('App', () => {
  beforeEach(() => {
    window.localStorage.clear()
    window.history.pushState({}, '', '/')
  })

  it('renders the landing page with brand, search, personas, and disclaimer', async () => {
    mockApi()
    render(<App />)
    expect(screen.getByText('Shortcut')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Starting from scratch/ })).toBeInTheDocument()
    expect(screen.getByRole('combobox')).toBeInTheDocument()
    expect(screen.getByText(/Not affiliated with Arkansas Tech University/)).toBeInTheDocument()
  })

  it('shows trust badges and filters majors by search', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    const input = await screen.findByRole('combobox')
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(2))
    await user.type(input, 'music')
    expect(screen.getAllByRole('option')).toHaveLength(1)
    expect(screen.getByText('Needs review')).toBeInTheDocument()
  })

  it('opens a persona plan with the comparison headline', async () => {
    mockApi()
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: /Starting from scratch/ }))
    expect(await screen.findByRole('heading', { name: 'Computer Science' })).toBeInTheDocument()
    expect(screen.getByText('Your Shortcut')).toBeInTheDocument()
    expect(window.location.pathname).toBe('/plan')
    expect(window.location.search).toContain('s=')
    expect(window.localStorage.getItem('shortcut.plan.v1')).toContain('computer-science-2025-26')
  })
})
