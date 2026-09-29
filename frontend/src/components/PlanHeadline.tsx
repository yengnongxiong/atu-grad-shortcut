import type { PlanResponse } from '../api/types'
import { formatTerms } from '../format'
import { TrustBadge } from './ui'

function Stat({ label, value, sub, tone = 'neutral' }: { label: string; value: string; sub?: string; tone?: 'neutral' | 'saved' }) {
  return (
    <div className={`rounded-md border bg-surface p-4 ${tone === 'saved' ? 'border-ink' : 'border-line'}`}>
      <p className={`text-sm ${tone === 'saved' ? 'font-medium text-ink' : 'text-muted'}`}>{label}</p>
      <p className="mt-1 text-3xl font-semibold">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  )
}

function shortcutSub(plan: PlanResponse, sooner: number, soonerMap: number): string {
  if (!plan.graduation) return plan.infeasible_reason ?? ''
  if (sooner > 0) {
    return `${formatTerms(sooner)} sooner than standard pace${soonerMap > sooner ? `, ${formatTerms(soonerMap)} vs. the map` : ''}`
  }
  if (soonerMap > 0) return `${formatTerms(soonerMap)} sooner than the degree map`
  if (soonerMap < 0) return `${formatTerms(-soonerMap)} later than the degree map`
  return plan.pace_note ? 'Same as standard pace; see why below' : 'Toggle levers to look for a faster path'
}

export function PlanHeadline({ plan }: { plan: PlanResponse }) {
  const sooner = plan.terms_sooner_than_standard ?? 0
  const soonerMap = plan.terms_sooner_than_map ?? 0
  const gained = sooner > 0 || soonerMap > 0
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
          tone={gained ? 'saved' : 'neutral'}
          value={plan.graduation?.date_label ?? 'No plan'}
          sub={shortcutSub(plan, sooner, soonerMap)}
        />
      </div>
      {plan.pace_note && (
        <p role="note" className="rounded-md border border-line-strong bg-paper-deep px-4 py-3 text-sm text-ink-soft">
          <strong className="text-ink">{soonerMap < 0 && sooner <= 0 ? 'Why you’re behind the map: ' : 'No shortcut here: '}</strong>
          {plan.pace_note}
        </p>
      )}
    </section>
  )
}
