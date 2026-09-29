import { render, screen } from '@testing-library/react'
import { SAMPLE_AUDIT } from '../degreeworks/fixtures/sample-audit'
import { parseAudit } from '../degreeworks/parse'
import { course, samplePlan } from '../test/fixtures'
import { AuditCheck } from './AuditCheck'

const audit = parseAudit(SAMPLE_AUDIT)

it('summarizes where Degree Works and the plan agree and differ', () => {
  const plan = samplePlan()
  const withCourses = {
    ...plan,
    terms: plan.terms
      .slice(0, 1)
      .map((term) => ({ ...term, courses: [course({ item_id: 'a', label: 'COMS 3213' }), course({ item_id: 'b', label: 'COMS 3053' })] })),
  }
  render(<AuditCheck audit={audit} plan={withCourses} />)
  expect(screen.getByText('Degree Works and this plan agree on 1 of 5 remaining requirements.')).toBeInTheDocument()
  expect(screen.getByText(/Capstone/)).toBeInTheDocument()
  expect(screen.getByText(/COMS 3053/)).toBeInTheDocument()
  expect(screen.getByText(/70 credits applied in Degree Works/)).toBeInTheDocument()
})
