import type { PlanResponse } from '../api/types'
import { formatTerms } from '../format'
import { TrustBadge } from './ui'

function Stat({ label, value, sub, tone = 'neutral' }: { label: string; value: string; sub?: string; tone?: 'neutral' | 'saved' }) {
  return (
    <div className={`rounded-xl border p-4 ${tone === 'saved' ? 'border-saved/40 bg-saved-soft' : 'border-line bg-surface'}`}>
      <p className={`text-xs font-semibold uppercase tracking-wider ${tone === 'saved' ? 'text-saved' : 'text-muted'}`}>{label}</p>
      <p className={`mt-1 font-display text-3xl font-semibold ${tone === 'saved' ? 'text-saved' : ''}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  )
}

export function PlanHeadline({ plan }: { plan: PlanResponse }) {
  const sooner = plan.terms_sooner_than_standard ?? 0
  const soonerMap = plan.terms_sooner_than_map ?? 0
  const summary = plan.graduation
    ? `Degree map: ${plan.degree_map.graduation?.date_label ?? '—'} · Standard pace: ${
        plan.standard_pace.graduation?.date_label ?? '—'
      } · Your Shortcut: ${plan.graduation.date_label}${sooner > 0 ? ` · ${formatTerms(sooner)} sooner` : ''}`
    : 'No valid plan under these settings'
  return (
    <section aria-labelledby="plan-title" className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="eyebrow">
          {plan.program.degree_abbr || plan.program.degree} · {plan.program.catalog_year} catalog · {plan.program.college}
        </p>
        <TrustBadge tier={plan.program.trust_tier} />
      </div>
      <h1 id="plan-title" className="text-3xl font-semibold sm:text-4xl">
        {plan.program.name}
      </h1>
      <p className="sr-only" aria-live="polite">
        {summary}
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Degree map" value={plan.degree_map.graduation?.date_label ?? '—'} sub="8 semesters from your first term" />
        <Stat label="Standard pace" value={plan.standard_pace.graduation?.date_label ?? '—'} sub="Fall/spring only, your preferred hours" />
        <Stat
          label="Your Shortcut"
          tone="saved"
          value={plan.graduation?.date_label ?? 'No plan'}
          sub={
            plan.graduation
              ? sooner > 0
                ? `${formatTerms(sooner)} sooner than standard pace${soonerMap > sooner ? `, ${formatTerms(soonerMap)} vs. the map` : ''}`
                : soonerMap > 0
                  ? `${formatTerms(soonerMap)} sooner than the degree map`
                  : 'Toggle levers to look for a faster path'
              : plan.infeasible_reason ?? ''
          }
        />
      </div>
    </section>
  )
}
