import { render, screen } from '@testing-library/react'
import { defaultLevers, defaultProfile } from '../state/profile'
import { samplePlan } from '../test/fixtures'
import { CourseActions } from './BottleneckGraph'

it('links the selected course to its ATU catalog entry', () => {
  const nodes = samplePlan().graph_nodes
  const node = nodes.find((n) => n.label === 'MATH 2914') ?? null
  render(<CourseActions node={node} nodes={nodes} onPick={() => {}} request={{ profile: defaultProfile('x'), levers: defaultLevers() }} />)
  expect(screen.getByRole('link', { name: /View MATH 2914 in the ATU catalog/ })).toHaveAttribute(
    'href',
    'https://catalog.atu.edu/search/?P=MATH%202914',
  )
})
