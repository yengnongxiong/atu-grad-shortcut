import type { LeverResult, Levers } from '../api/types'
import { formatTerms } from '../format'
import { Tag, Toggle } from './ui'

const ORDER: LeverResult['id'][] = [
  'heavier_terms',
  'summer',
  'winter',
  'overload',
  'aggressive_overload',
  'transfer_summer',
  'planned_exams',
]

export function LeverPanel({
  levers,
  results,
  busy,
  onToggle,
  onOpenExams,
}: {
  levers: Levers
  results: LeverResult[]
  busy: boolean
  onToggle: (id: Exclude<LeverResult['id'], 'planned_exams'>, value: boolean) => void
  onOpenExams: () => void
}) {
  const byId = new Map(results.map((r) => [r.id, r]))
  return (
    <section aria-labelledby="levers-title" className="card p-4">
      <div className="flex items-baseline justify-between">
        <h2 id="levers-title" className="text-xl font-semibold">
          Acceleration levers
        </h2>
        {busy && <span className="text-xs text-muted">Re-solving…</span>}
      </div>
      <p className="mt-1 text-xs text-muted">
        “Saves” is marginal: your full plan vs. the same plan with only that lever off. Levers can overlap.
      </p>
      <ul className="mt-3 divide-y divide-line">
        {ORDER.map((id) => {
          const result = byId.get(id)
          if (!result) return null
          const isExams = id === 'planned_exams'
          const checked = isExams ? levers.planned_exams.length > 0 : Boolean(levers[id as keyof Omit<Levers, 'planned_exams'>])
          const descId = `lever-${id}-desc`
          const saved = result.terms_saved
          return (
            <li key={id} className="py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold leading-tight">{result.label}</p>
                  <p id={descId} className="mt-0.5 text-xs text-muted">
                    {result.workload}
                    {result.policy_key && (
                      <>
                        {' '}
                        <a href={`/about#policy-${result.policy_key}`}>Policy</a>
                      </>
                    )}
                  </p>
                </div>
                {isExams ? (
                  <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={onOpenExams}>
                    {checked ? `${levers.planned_exams.length} planned` : 'Choose'}
                  </button>
                ) : (
                  <Toggle
                    checked={checked}
                    disabled={!result.available || busy}
                    label={result.label}
                    describedBy={descId}
                    onChange={(value) => onToggle(id as Exclude<LeverResult['id'], 'planned_exams'>, value)}
                  />
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {checked && saved !== null && (
                  <Tag tone={saved > 0 ? 'saved' : 'neutral'}>{saved > 0 ? `Saves ${formatTerms(saved)}` : 'No time saved alone'}</Tag>
                )}
                <Tag title="Cost">{result.cost === 'none' ? 'No extra cost' : result.cost}</Tag>
                <Tag tone={result.approval === 'none' ? 'neutral' : 'warn'} title="Approval">
                  {result.approval === 'none' ? 'No approval' : `Approval: ${result.approval}`}
                </Tag>
              </div>
              {!result.available && <p className="mt-2 text-xs text-warn">{result.note}</p>}
            </li>
          )
        })}
      </ul>
      <div className="mt-2 rounded-md border border-dashed border-line-strong bg-paper p-3 text-sm">
        <p className="font-semibold">Credit for Prior Learning</p>
        <p className="mt-1 text-xs text-ink-soft">
          Work experience, certifications, military training, or a department exam may earn credit. It’s decided case by case,
          so Shortcut never schedules it: ask your department.{' '}
          <a href="https://www.atu.edu/cpl/students.php" target="_blank" rel="noreferrer">
            ATU CPL
          </a>
        </p>
      </div>
    </section>
  )
}
