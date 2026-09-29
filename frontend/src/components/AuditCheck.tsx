import type { PlanResponse } from '../api/types'
import { formatHours } from '../format'
import { reconcile } from '../degreeworks/reconcile'
import type { AuditImport } from '../degreeworks/types'

/** Degree Works vs. the plan: agreement plus the differences worth raising with an advisor. */
export function AuditCheck({ audit, plan }: { audit: AuditImport; plan: PlanResponse }) {
  const r = reconcile(audit, plan)
  if (r.total === 0) return null
  return (
    <section className="card p-4 text-sm" aria-label="Degree Works check">
      <p className="font-semibold">
        Degree Works and this plan agree on {r.agree} of {r.total} remaining requirements.
      </p>
      <p className="mt-1 text-muted">
        {r.creditsAudit !== null ? `${formatHours(r.creditsAudit)} credits applied in Degree Works · ` : ''}
        {formatHours(r.creditsShortcut)} credited in Shortcut
      </p>
      {(r.onlyInAudit.length > 0 || r.onlyInPlan.length > 0) && (
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          {r.onlyInAudit.length > 0 && (
            <div>
              <p className="font-medium">Still needed in Degree Works, not in this plan</p>
              <p className="mt-1 text-ink-soft">
                {r.onlyInAudit
                  .map((need) => `${need.label || 'Requirement'}${need.codes.length > 0 && need.codes.length <= 4 ? ` (${need.codes.join(', ')})` : ''}`)
                  .join('; ')}
              </p>
            </div>
          )}
          {r.onlyInPlan.length > 0 && (
            <div>
              <p className="font-medium">In this plan, not listed as still needed</p>
              <p className="mt-1 text-ink-soft">{r.onlyInPlan.map((item) => item.label).join(', ')}</p>
            </div>
          )}
        </div>
      )}
      <p className="mt-3 text-xs text-muted">
        Differences usually mean the degree map and Degree Works list requirements differently, or a course the plan adds for a prerequisite. Bring
        them to your advisor; Degree Works is the official record.
      </p>
    </section>
  )
}
