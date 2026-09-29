import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { MetaResponse, PolicyOut, ProgramListItem } from '../api/types'
import { DISCLAIMER } from '../components/Layout'
import { ErrorBox, Spinner, TrustBadge } from '../components/ui'
import { CONFIDENCE_LABEL, TIER_HELP, TIER_LABEL } from '../format'

function formatValue(policy: PolicyOut): string {
  const value = policy.value
  if (Array.isArray(value)) return value.join(policy.key === 'workload_outside_per_credit' ? '–' : ', ')
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => typeof v !== 'object')
      .map(([k, v]) => `${k}: ${String(v)}`)
      .join(' · ')
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

const CONFIDENCE_TONE: Record<string, string> = {
  documented: 'border-saved/40 bg-saved-soft text-saved',
  derived: 'border-info/30 bg-info-soft text-info',
  assumed: 'border-warn/40 bg-warn-soft text-warn',
  unknown: 'border-line-strong bg-paper text-muted',
  conflicting: 'border-critical/40 bg-critical-soft text-critical',
}

export function About({ programs }: { programs: ProgramListItem[] }) {
  const [meta, setMeta] = useState<MetaResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .meta()
      .then(setMeta)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
  }, [])

  useEffect(() => {
    if (!meta || !window.location.hash) return
    document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: 'center' })
  }, [meta])

  if (error) return <div className="mx-auto max-w-4xl px-4 py-10"><ErrorBox message={error} /></div>
  if (!meta) return <div className="mx-auto max-w-4xl px-4 py-10"><Spinner label="Loading data sources…" /></div>

  const bachelors = programs.length
  const good = programs.filter((p) => p.trust_tier !== 'needs_review').length
  return (
    <div className="mx-auto max-w-5xl space-y-10 px-4 py-10 sm:px-6">
      <header>
        <p className="eyebrow">About the data</p>
        <h1 className="mt-1 text-4xl font-semibold">Where every number comes from</h1>
        <p className="mt-3 max-w-3xl text-ink-soft">
          Shortcut only uses public ATU sources. Each course, requirement, policy, and exam equivalency traces to one of them, and every
          inference carries a confidence label: <em>documented</em>, <em>derived</em>, <em>assumed</em>, <em>unknown</em>, or{' '}
          <em>conflicting</em>.
        </p>
        <p className="mt-3 rounded-lg border border-line-strong bg-surface p-3 font-semibold">{DISCLAIMER}</p>
      </header>

      <section aria-labelledby="coverage">
        <h2 id="coverage" className="text-2xl font-semibold">Coverage</h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-4">
          {[
            ['Catalog year', meta.newest_catalog_year],
            ['Last pipeline run', new Date(meta.generated_at).toLocaleString()],
            ['Degree maps found', String(meta.discovered_maps)],
            ['Courses', String(meta.course_count)],
          ].map(([label, value]) => (
            <div key={label} className="card p-3">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="font-display text-xl font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {(['cross_checked', 'auto_imported', 'needs_review'] as const).map((tier) => (
            <div key={tier} className="card p-3">
              <TrustBadge tier={tier} compact />
              <p className="mt-2 font-display text-3xl font-semibold">{meta.tier_counts[tier] ?? 0}</p>
              <p className="text-xs text-muted">{TIER_HELP[tier]}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-sm text-ink-soft">
          {good} of {bachelors} bachelor’s programs pass every automated check ({bachelors ? Math.round((100 * good) / bachelors) : 0}%).
          Associate degrees ({meta.tier_counts.excluded ?? 0}) are listed in the pipeline report but not planned (PRD non-goal).
        </p>
        <p className="mt-2 text-sm text-muted">catalog.atu.edu: {meta.catalog_status}. Banner: {meta.banner_status}.</p>
      </section>

      <section aria-labelledby="sources">
        <h2 id="sources" className="text-2xl font-semibold">Sources</h2>
        <ul className="mt-3 space-y-1.5 text-sm">
          {meta.sources.map((s) => (
            <li key={s.url}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title}
              </a>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-ink-soft">
          Exam tables: {Object.entries(meta.exam_programs).map(([k, v]) => `${k} ${v}`).join(' · ')}. AP and IB course tables are only on
          the catalog site, which couldn’t be reached when the data was built, so they aren’t guessed.
        </p>
      </section>

      <section aria-labelledby="policies">
        <h2 id="policies" className="text-2xl font-semibold">Policies</h2>
        <p className="mt-1 text-sm text-muted">Every policy number the planner uses. Warnings in your plan link here.</p>
        <div className="mt-4 overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[44rem] text-sm">
            <thead className="bg-paper-deep text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-3 py-2">Rule</th>
                <th scope="col" className="px-3 py-2">Value</th>
                <th scope="col" className="px-3 py-2">Confidence</th>
                <th scope="col" className="px-3 py-2">Sources</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {meta.policies.map((p) => (
                <tr key={p.key} id={`policy-${p.key}`} className="scroll-mt-24 target:bg-warn-soft">
                  <th scope="row" className="px-3 py-2 text-left align-top font-semibold">
                    {p.label}
                    {p.note && <span className="mt-1 block text-xs font-normal text-muted">{p.note}</span>}
                  </th>
                  <td className="px-3 py-2 align-top">
                    {formatValue(p)} <span className="text-xs text-muted">{p.unit}</span>
                  </td>
                  <td className="px-3 py-2 align-top">
                    <span className={`chip ${CONFIDENCE_TONE[p.confidence] ?? ''}`}>{CONFIDENCE_LABEL[p.confidence] ?? p.confidence}</span>
                  </td>
                  <td className="px-3 py-2 align-top text-xs">
                    {p.sources.map((s) =>
                      s.url ? (
                        <a key={s.title} href={s.url} target="_blank" rel="noreferrer" className="block">
                          {s.title}
                        </a>
                      ) : (
                        <span key={s.title} className="block text-muted">
                          {s.title}
                        </span>
                      ),
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="assumptions">
        <h2 id="assumptions" className="text-2xl font-semibold">Assumptions</h2>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-ink-soft">
          {meta.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="programs-list">
        <h2 id="programs-list" className="text-2xl font-semibold">Programs by trust tier</h2>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {programs.map((p) => (
            <li key={p.id} className="flex items-start justify-between gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm">
              <span>
                <span className="font-medium">{p.listed_title}</span>
                <span className="block text-xs text-muted">
                  {p.catalog_year} · {p.college}
                </span>
                {p.issues.length > 0 && (
                  <details className="mt-1 text-xs text-muted">
                    <summary className="cursor-pointer">{p.issues.length} issue(s)</summary>
                    <ul className="mt-1 list-disc pl-4">
                      {p.issues.map((i) => (
                        <li key={i}>{i}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </span>
              <span className="shrink-0" title={TIER_LABEL[p.trust_tier]}>
                <TrustBadge tier={p.trust_tier} compact />
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
