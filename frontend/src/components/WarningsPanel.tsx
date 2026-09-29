import { useState } from 'react'
import type { PlanWarning } from '../api/types'

const GROUPS: { key: PlanWarning['category']; title: string }[] = [
  { key: 'policy', title: 'Policy checks' },
  { key: 'data', title: 'Data quality' },
  { key: 'plan', title: 'Plan notes' },
]

const SEVERITY: Record<PlanWarning['severity'], { label: string; className: string }> = {
  error: { label: 'Problem', className: 'border-error text-error' },
  warning: { label: 'Check', className: 'border-ink text-ink' },
  info: { label: 'Note', className: '' },
}

function WarningItem({ warning }: { warning: PlanWarning }) {
  const severity = SEVERITY[warning.severity]
  return (
    <li className="flex gap-2 text-sm">
      <span className={`chip mt-0.5 h-5 w-16 shrink-0 justify-center ${severity.className}`}>{severity.label}</span>
      <span>
        {warning.message}{' '}
        {warning.policy_key && (
          <a href={`/about#policy-${warning.policy_key}`} className="text-xs">
            Policy
          </a>
        )}
        {warning.source?.url && (
          <>
            {' '}
            <a href={warning.source.url} target="_blank" rel="noreferrer" className="text-xs">
              Source
            </a>
          </>
        )}
      </span>
    </li>
  )
}

export function WarningsPanel({ warnings, assumptions }: { warnings: PlanWarning[]; assumptions: string[] }) {
  const [showAll, setShowAll] = useState(false)
  const important = warnings.filter((w) => w.severity !== 'info')
  const visible = showAll ? warnings : important.length > 0 ? important : warnings.slice(0, 4)
  return (
    <section aria-labelledby="warnings-title" className="card p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="warnings-title" className="text-xl font-semibold">
          Warnings & assumptions
        </h2>
        {warnings.length > visible.length || showAll ? (
          <button type="button" className="text-xs font-semibold underline" onClick={() => setShowAll((s) => !s)}>
            {showAll ? 'Show fewer' : `Show all ${warnings.length}`}
          </button>
        ) : null}
      </div>
      {GROUPS.map((group) => {
        const items = visible.filter((w) => w.category === group.key)
        if (items.length === 0) return null
        return (
          <div key={group.key} className="mt-3">
            <h3 className="eyebrow">{group.title}</h3>
            <ul className="mt-2 space-y-2">
              {items.map((w) => (
                <WarningItem key={w.id} warning={w} />
              ))}
            </ul>
          </div>
        )
      })}
      <details className="mt-4 rounded-md border border-line bg-paper p-3 text-sm">
        <summary className="cursor-pointer font-semibold">Assumptions behind this plan ({assumptions.length})</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-ink-soft">
          {assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </details>
    </section>
  )
}
