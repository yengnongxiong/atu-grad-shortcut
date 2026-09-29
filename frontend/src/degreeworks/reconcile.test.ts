import type { PlanResponse } from '../api/types'
import { course, samplePlan } from '../test/fixtures'
import { SAMPLE_AUDIT } from './fixtures/sample-audit'
import { parseAudit } from './parse'
import { reconcile } from './reconcile'

const audit = parseAudit(SAMPLE_AUDIT)

function planWith(courses: ReturnType<typeof course>[]): PlanResponse {
  const plan = samplePlan()
  return {
    ...plan,
    terms: plan.terms.slice(0, 1).map((term) => ({ ...term, courses })),
    credited: [
      { code: 'TECH 1001', title: '', hours: 1, source: 'atu', grade: 'B', requirement_id: null, counts_toward: '' },
      { code: 'ENGL 1013', title: '', hours: 39, source: 'exam', grade: null, requirement_id: null, counts_toward: '' },
    ],
  }
}

const elective = (n: number) => course({ item_id: `e${n}`, label: 'Approved Elective (3000-4000 level)', kind: 'elective' })
const fullPlan = [
  course({ item_id: 'a', label: 'COMS 3213' }),
  course({ item_id: 'b', label: 'COMS 4913' }),
  course({ item_id: 'c', label: 'COMS 3053' }),
  course({ item_id: 'd', label: 'Science with Lab', kind: 'bucket', options: ['BIOL 1014', 'BIOL 1004', 'PHSC 1004', 'GEOL 1014'] }),
  course({ item_id: 'f', label: 'Social Sciences', kind: 'bucket', options: ['HIST 1503', 'PSY 2003', 'SOC 1003'] }),
  elective(1),
  elective(2),
]

describe('reconcile', () => {
  it('agrees when every still-needed line has a planned course, bucket, or elective', () => {
    const r = reconcile(audit, planWith(fullPlan))
    expect([r.agree, r.total]).toEqual([5, 5])
    expect(r.onlyInAudit).toEqual([])
  })

  it('lists planned work that no still-needed line covers', () => {
    expect(reconcile(audit, planWith(fullPlan)).onlyInPlan).toEqual([{ code: 'COMS 3053', label: 'COMS 3053' }])
  })

  it('lists still-needed lines the plan does not cover', () => {
    const r = reconcile(audit, planWith(fullPlan.filter((c) => c.label !== 'COMS 4913')))
    expect([r.agree, r.total]).toEqual([4, 5])
    expect(r.onlyInAudit.map((s) => s.label)).toEqual(['Capstone'])
  })

  it('uses each planned item for one line only', () => {
    const science = audit.stillNeeded.filter((s) => s.label === 'SCIENCE WITH LAB COURSE')
    const twoScience = { ...audit, stillNeeded: [...science, ...science] }
    const r = reconcile(twoScience, planWith(fullPlan.filter((c) => c.label === 'Science with Lab')))
    expect([r.agree, r.total]).toEqual([1, 2])
  })

  it('compares credits applied', () => {
    const r = reconcile(audit, planWith(fullPlan))
    expect([r.creditsAudit, r.creditsShortcut]).toEqual([40, 40])
  })
})
