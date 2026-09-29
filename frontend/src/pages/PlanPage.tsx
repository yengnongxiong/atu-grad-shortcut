import { lazy, Suspense, useState } from 'react'
import type { Levers, PlanRequest, ProgramListItem } from '../api/types'
import { AdvisorExport } from '../components/AdvisorExport'
import { ExamOpportunities } from '../components/ExamOpportunities'
import { LeverPanel } from '../components/LeverPanel'
import { PlanHeadline } from '../components/PlanHeadline'
import { Timeline } from '../components/Timeline'
import { ErrorBox, Spinner } from '../components/ui'
import { WarningsPanel } from '../components/WarningsPanel'
import { WhatIfPanel } from '../components/WhatIfPanel'
import { navigate } from '../router'
import { usePlan } from '../state/usePlan'

const BottleneckGraph = lazy(() => import('../components/BottleneckGraph').then((m) => ({ default: m.BottleneckGraph })))

type PlanTab = 'plan' | 'bottlenecks' | 'exams' | 'whatif' | 'export'

const TABS: { id: PlanTab; label: string }[] = [
  { id: 'plan', label: 'Plan' },
  { id: 'bottlenecks', label: 'Bottlenecks' },
  { id: 'exams', label: 'Exam opportunities' },
  { id: 'whatif', label: 'What-if' },
  { id: 'export', label: 'Advisor export' },
]

export function PlanPage({
  request,
  programs,
  onChange,
}: {
  request: PlanRequest | null
  programs: ProgramListItem[]
  onChange: (request: PlanRequest) => void
}) {
  const { plan, loading, error, retry } = usePlan(request)
  const [tab, setTab] = useState<PlanTab>('plan')

  if (!request || !request.profile.program_id) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <h1 className="text-3xl font-semibold">No plan yet</h1>
        <p className="mt-2 text-ink-soft">Pick a major (or a demo profile) to build one.</p>
        <button type="button" className="btn-primary mt-6" onClick={() => navigate('landing')}>
          Choose a major
        </button>
      </div>
    )
  }

  const setLever = (id: keyof Omit<Levers, 'planned_exams'>, value: boolean) => {
    const levers = { ...request.levers, [id]: value }
    if (id === 'aggressive_overload' && value) levers.overload = true
    if (id === 'overload' && !value) levers.aggressive_overload = false
    onChange({ ...request, levers })
  }
  const setPlannedExam = (examId: string, value: boolean) => {
    const set = new Set(request.levers.planned_exams)
    if (value) set.add(examId)
    else set.delete(examId)
    onChange({ ...request, levers: { ...request.levers, planned_exams: [...set] } })
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="no-print mb-4 flex flex-wrap items-center justify-between gap-2">
        <button type="button" className="btn-ghost -ml-3" onClick={() => navigate('setup')}>
          ← Edit profile
        </button>
        {loading && plan && <Spinner label="Re-solving…" />}
      </div>

      {error && <ErrorBox message={error} onRetry={retry} />}
      {!plan && !error && (
        <div className="py-20">
          <Spinner label="Solving thousands of possible schedules…" />
        </div>
      )}

      {plan && (
        <div className="space-y-6">
          <div className="no-print">
            <PlanHeadline plan={plan} />
          </div>
          {plan.program.trust_tier === 'needs_review' && (
            <div role="note" className="no-print rounded-lg border border-warn/50 bg-warn-soft p-3 text-sm text-warn">
              <strong>Needs review:</strong> automated checks found problems in this program’s data. Treat this plan as a sketch and
              compare it with the degree map.
            </div>
          )}

          <div role="tablist" aria-label="Plan views" className="no-print flex flex-wrap gap-1 border-b border-line">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                id={`tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls={`panel-${t.id}`}
                type="button"
                onClick={() => setTab(t.id)}
                className={`-mb-px border-b-2 px-3 py-2 text-sm font-semibold ${
                  tab === t.id ? 'border-ink text-ink' : 'border-transparent text-muted hover:text-ink'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === 'plan' &&
              (plan.feasible ? (
                <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
                  <div className="min-w-0 space-y-6">
                    <Timeline terms={plan.terms} credited={plan.credited} />
                    <WarningsPanel warnings={plan.warnings} assumptions={plan.assumptions} />
                  </div>
                  <LeverPanel
                    levers={request.levers}
                    results={plan.levers}
                    busy={loading}
                    onToggle={setLever}
                    onOpenExams={() => setTab('exams')}
                  />
                </div>
              ) : (
                <div className="grid gap-6 xl:grid-cols-[1fr_22rem]">
                  <ErrorBox message={plan.infeasible_reason ?? 'No valid plan under these settings.'} />
                  <LeverPanel
                    levers={request.levers}
                    results={plan.levers}
                    busy={loading}
                    onToggle={setLever}
                    onOpenExams={() => setTab('exams')}
                  />
                </div>
              ))}
            {tab === 'bottlenecks' && (
              <Suspense fallback={<Spinner label="Loading the graph…" />}>
                <BottleneckGraph plan={plan} request={request} />
              </Suspense>
            )}
            {tab === 'exams' && <ExamOpportunities request={request} onTogglePlanned={setPlannedExam} />}
            {tab === 'whatif' && plan.feasible && <WhatIfPanel plan={plan} request={request} programs={programs} />}
            {tab === 'export' && plan.feasible && <AdvisorExport plan={plan} request={request} />}
          </div>
          <p className="no-print text-right text-xs text-muted">
            Solved in {(plan.stats.solve_ms / 1000).toFixed(1)} s ({plan.stats.solves} solves)
            {plan.stats.timed_out ? ' · hit the time limit; showing the best plan found' : ''}
          </p>
        </div>
      )}
    </div>
  )
}
