import type { PlanResponse, PlannedCourse } from '../api/types'
import type { AuditImport, StillNeeded } from './types'

export interface Reconciliation {
  agree: number
  total: number
  /** Degree Works still needs it, and no planned course, bucket, or elective covers it. */
  onlyInAudit: StillNeeded[]
  /** Planned, but no still-needed line covers it (added prerequisites, filler hours, …). */
  onlyInPlan: { code: string | null; label: string }[]
  creditsAudit: number | null
  creditsShortcut: number
}

const UPPER_LEVEL_SLOT = /3000|4000|upper[- ]level/i

function covers(need: StillNeeded, item: PlannedCourse): boolean {
  if (need.anyUpperLevel) return item.kind !== 'course' && UPPER_LEVEL_SLOT.test(item.label)
  if (item.code && need.codes.includes(item.code)) return true
  return item.options.some((code) => need.codes.includes(code))
}

/**
 * Compare Degree Works' "still needed" lines with Shortcut's plan. Each planned item covers at
 * most one line, except that a generic 3000–4000 elective line covers every upper-level slot.
 * Specific lines are matched first so a broad line can't take a course a narrow one needs.
 */
export function reconcile(audit: AuditImport, plan: PlanResponse): Reconciliation {
  const planned = plan.terms.flatMap((t) => t.courses)
  const used = new Set<string>()
  const order = audit.stillNeeded
    .map((need, index) => ({ need, index }))
    .sort((a, b) => Number(a.need.anyUpperLevel) - Number(b.need.anyUpperLevel) || a.need.codes.length - b.need.codes.length)
  const matched = new Set<number>()
  for (const { need, index } of order) {
    const hits = planned.filter((item) => !used.has(item.item_id) && covers(need, item))
    if (!hits.length) continue
    matched.add(index)
    for (const hit of need.anyUpperLevel ? hits : hits.slice(0, 1)) used.add(hit.item_id)
  }
  return {
    agree: matched.size,
    total: audit.stillNeeded.length,
    onlyInAudit: audit.stillNeeded.filter((_, index) => !matched.has(index)),
    onlyInPlan: planned.filter((item) => !used.has(item.item_id)).map((item) => ({ code: item.code, label: item.label })),
    creditsAudit: audit.creditsApplied,
    creditsShortcut: plan.credited.reduce((sum, c) => sum + c.hours, 0),
  }
}
