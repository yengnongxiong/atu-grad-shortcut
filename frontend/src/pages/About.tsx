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

const SOURCES: [string, string, string][] = [
  [
    'ATU academic catalog',
    'The rules: prerequisites, AP/CLEP/IB credit, graduation and load policies.',
    'Credit tables and policies saved from the catalog; each course links to its catalog entry.',
  ],
  [
    'Degree maps (per catalog year)',
    'The average path: 8 semesters for a first-time freshman admitted that year.',
    'Every bachelor’s map from 2025–26 on; you plan against the map for the year you started.',
  ],
  [
    'Degree Works',
    'The official record: what’s done, in progress, and still needed.',
    'Import your audit (read on your device) and see where it and the plan agree.',
  ],
  [
    'Shortcut',
    'When and in what order: the fastest realistic finish and what each option costs.',
    'A planning aid for the advisor conversation, not an official audit.',
  ],
]

const TIER_COLUMNS = [
  ['cross_checked', 'Cross-checked'],
  ['auto_imported', 'Auto-imported'],
  ['needs_review', 'Needs review'],
  ['excluded', 'Associate (not planned)'],
] as const

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

  const snapshots = meta.catalog_snapshots ?? []
  const savedOn = [...new Set(snapshots.map((s) => s.captured_at))].sort().join(', ')
  const sources = SOURCES.map(([name, answers, uses], i) =>
    i === 0 && savedOn ? ([name, answers, `${uses} Saved ${savedOn}.`] as const) : ([name, answers, uses] as const),
  )
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
        <p className="mt-3 rounded-md border border-line-strong bg-surface p-3 font-semibold">{DISCLAIMER}</p>
      </header>

      <section aria-labelledby="fits">
        <h2 id="fits" className="text-2xl font-semibold">Where Shortcut fits</h2>
        <p className="mt-2 max-w-3xl text-sm text-ink-soft">
          ATU students already have three official planning tools. Each answers part of the question, and Shortcut starts from all three.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="border-b border-line text-xs text-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">Source</th>
                <th className="py-2 pr-4 font-medium">What it answers</th>
                <th className="py-2 font-medium">How Shortcut uses it</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line align-top">
              {sources.map(([name, answers, uses]) => (
                <tr key={name}>
                  <td className="py-2 pr-4 font-medium">{name}</td>
                  <td className="py-2 pr-4 text-ink-soft">{answers}</td>
                  <td className="py-2 text-ink-soft">{uses}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="coverage">
        <h2 id="coverage" className="text-2xl font-semibold">Coverage</h2>
        <dl className="mt-4 grid gap-3 sm:grid-cols-4">
          {[
            ['Catalog years', (meta.catalog_years ?? [meta.newest_catalog_year]).join(', ')],
            ['Last pipeline run', new Date(meta.generated_at).toLocaleString()],
            ['Degree maps found', String(meta.discovered_maps)],
            ['Courses', String(meta.course_count)],
          ].map(([label, value]) => (
            <div key={label} className="card p-3">
              <dt className="text-xs text-muted">{label}</dt>
              <dd className="text-xl font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {(['cross_checked', 'auto_imported', 'needs_review'] as const).map((tier) => (
            <div key={tier} className="card p-3">
              <TrustBadge tier={tier} compact />
              <p className="mt-2 text-3xl font-semibold">{meta.tier_counts[tier] ?? 0}</p>
              <p className="text-xs text-muted">{TIER_HELP[tier]}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-sm text-ink-soft">
          {good} of {bachelors} bachelor’s programs pass every automated check ({bachelors ? Math.round((100 * good) / bachelors) : 0}%).
          Associate degrees ({meta.tier_counts.excluded ?? 0}) are listed in the pipeline report but not planned (PRD non-goal).
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[32rem] text-left text-sm">
            <caption className="sr-only">Programs by catalog year and trust tier</caption>
            <thead className="border-b border-line text-xs text-muted">
              <tr>
                <th className="py-2 pr-4 font-medium">Catalog year</th>
                {TIER_COLUMNS.map(([tier, label]) => (
                  <th key={tier} className="py-2 pr-4 text-right font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {Object.entries(meta.tier_counts_by_year ?? {}).map(([year, counts]) => (
                <tr key={year}>
                  <th scope="row" className="py-2 pr-4 text-left font-medium">
                    {year}
                  </th>
                  {TIER_COLUMNS.map(([tier]) => (
                    <td key={tier} className="py-2 pr-4 text-right tabular-nums">
                      {counts[tier] ?? 0}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-sm text-muted">Banner: {meta.banner_status}.</p>
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
        {snapshots.length > 0 && (
          <>
            <h3 className="mt-5 font-semibold">Saved catalog pages</h3>
            <ul className="mt-2 space-y-1.5 text-sm">
              {snapshots.map((s) => (
                <li key={s.url}>
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.title}
                  </a>{' '}
                  <span className="text-muted">
                    ({s.catalog_edition} catalog, saved {s.captured_at})
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="mt-3 text-sm text-ink-soft">
          Exam tables: {Object.entries(meta.exam_programs).map(([k, v]) => `${k} ${v}`).join(' · ')}. The AP, CLEP, and IB tables come from
          the 2026–27 catalog, saved from a regular browser because the catalog site blocks automated tools. Rows that award generic
          credit (for example “3 hours General Education Humanities”) aren’t mapped to a course.
        </p>
      </section>

      <section aria-labelledby="policies">
        <h2 id="policies" className="text-2xl font-semibold">Policies</h2>
        <p className="mt-1 text-sm text-muted">Every policy number the planner uses. Warnings in your plan link here.</p>
        <div className="mt-4 overflow-x-auto rounded-md border border-line">
          <table className="w-full min-w-[44rem] text-sm">
            <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-3 py-2">Rule</th>
                <th scope="col" className="px-3 py-2">Value</th>
                <th scope="col" className="px-3 py-2">Confidence</th>
                <th scope="col" className="px-3 py-2">Sources</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {meta.policies.map((p) => (
                <tr key={p.key} id={`policy-${p.key}`} className="scroll-mt-24 target:bg-paper-deep">
                  <th scope="row" className="px-3 py-2 text-left align-top font-semibold">
                    {p.label}
                    {p.note && <span className="mt-1 block text-xs font-normal text-muted">{p.note}</span>}
                  </th>
                  <td className="px-3 py-2 align-top">
                    {formatValue(p)} <span className="text-xs text-muted">{p.unit}</span>
                  </td>
                  <td className="px-3 py-2 align-top">
                    <span className="chip">{CONFIDENCE_LABEL[p.confidence] ?? p.confidence}</span>
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
            <li key={p.id} className="flex items-start justify-between gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm">
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
