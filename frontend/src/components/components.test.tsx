import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { PlanRequest } from '../api/types'
import { defaultLevers, defaultProfile } from '../state/profile'
import { samplePlan } from '../test/fixtures'
import { AdvisorExport } from './AdvisorExport'
import { LeverPanel } from './LeverPanel'
import { PlanHeadline } from './PlanHeadline'
import { Timeline } from './Timeline'
import { WarningsPanel } from './WarningsPanel'

const request: PlanRequest = { profile: defaultProfile('computer-science-2025-26'), levers: { ...defaultLevers(), summer: true } }

describe('plan components', () => {
  it('headline compares degree map, standard pace, and the Shortcut', () => {
    render(<PlanHeadline plan={samplePlan()} />)
    expect(screen.getAllByText('May 2030')).toHaveLength(2)
    expect(screen.getByText('May 2029')).toBeInTheDocument()
    expect(screen.getByText(/2 terms sooner than standard pace/)).toBeInTheDocument()
  })

  it('timeline marks critical courses with an icon and text, not color alone', () => {
    render(<Timeline terms={samplePlan().terms} credited={[]} />)
    const fall = screen.getByRole('region', { name: /Fall 2026/ })
    expect(within(fall).getByText('Critical.')).toBeInTheDocument()
    expect(within(fall).getByText('C or better')).toBeInTheDocument()
    const summer = screen.getByRole('region', { name: /Summer 2027/ })
    expect(within(summer).getByText(/Unconfirmed offering/)).toBeInTheDocument()
    expect(within(fall).getByText(/hrs\/week/)).toBeInTheDocument()
  })

  it('lever panel shows marginal savings and blocks ineligible overloads', async () => {
    const onToggle = vi.fn()
    const user = userEvent.setup()
    render(<LeverPanel levers={request.levers} results={samplePlan().levers} busy={false} onToggle={onToggle} onOpenExams={() => undefined} />)
    expect(screen.getByText('Saves 2 terms')).toBeInTheDocument()
    const overload = screen.getByRole('switch', { name: /Overloads/ })
    expect(overload).toBeDisabled()
    await user.click(screen.getByRole('switch', { name: 'Summer terms' }))
    expect(onToggle).toHaveBeenCalledWith('summer', false)
    expect(screen.getByText(/Credit for Prior Learning/)).toBeInTheDocument()
  })

  it('warnings link to the policy on the About page and to the source', () => {
    render(<WarningsPanel warnings={samplePlan().warnings} assumptions={samplePlan().assumptions} />)
    expect(screen.getByRole('link', { name: 'Policy' })).toHaveAttribute('href', '/about#policy-exam_credit_cap_hours')
    expect(screen.getByRole('link', { name: 'Source' })).toHaveAttribute('href', 'https://www.atu.edu/admissions/credit.php')
  })

  it('advisor export lists levers, the disclaimer, and a share link', () => {
    render(<AdvisorExport plan={samplePlan()} request={request} />)
    expect(screen.getByText(/Summer terms/)).toBeInTheDocument()
    expect(screen.getAllByText(/Not affiliated with Arkansas Tech University/).length).toBeGreaterThan(0)
    expect((screen.getByLabelText('Share link') as HTMLInputElement).value).toContain('/plan?s=')
  })
})
