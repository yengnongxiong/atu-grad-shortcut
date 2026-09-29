import { useState } from 'react'
import type { PlanRequest, PlanResponse } from '../api/types'
import { SOURCE_LABEL, TIER_LABEL, formatHours, formatTerms } from '../format'
import { shareUrl } from '../state/profile'
import { DISCLAIMER } from './Layout'

export function AdvisorExport({ plan, request }: { plan: PlanResponse; request: PlanRequest }) {
  const [copied, setCopied] = useState(false)
  const link = shareUrl(request)
  const leversUsed = plan.levers.filter((l) => l.enabled)
  const petitions = [
    ...plan.terms
      .filter((t) => t.approval)
      .map((t) => ({ what: `${t.label}: ${formatHours(t.hours)}-hour load`, who: t.approval ?? '' })),
    ...leversUsed
      .filter((l) => l.approval !== 'none' && l.id !== 'overload' && l.id !== 'aggressive_overload')
      .map((l) => ({ what: l.label, who: l.approval })),
  ]
  const problems = plan.warnings.filter((w) => w.severity !== 'info')

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="no-print flex flex-wrap items-center gap-2">
        <button type="button" className="btn-primary" onClick={() => window.print()}>
          Print / save as PDF
        </button>
        <button type="button" className="btn-secondary" onClick={() => void copy()}>
          {copied ? 'Link copied' : 'Copy share link'}
        </button>
        <label className="sr-only" htmlFor="share-link">
          Share link
        </label>
        <input id="share-link" readOnly value={link} className="input max-w-md flex-1 font-mono text-xs" onFocus={(e) => e.target.select()} />
      </div>

      <article className="print-page card mx-auto max-w-4xl bg-surface p-6 text-[0.82rem] leading-snug">
        <header className="flex flex-wrap items-start justify-between gap-2 border-b border-line pb-3">
          <div>
            <p className="eyebrow">Shortcut plan · for discussion with an advisor</p>
            <h2 className="text-2xl font-semibold">{plan.program.name}</h2>
            <p className="text-muted">
              {plan.program.degree} · {plan.program.catalog_year} catalog · data: {TIER_LABEL[plan.program.trust_tier]}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xl font-semibold text-saved">Graduate {plan.graduation?.date_label ?? '—'}</p>
            <p className="text-muted">
              Map {plan.degree_map.graduation?.date_label ?? '—'} · standard pace {plan.standard_pace.graduation?.date_label ?? '—'}
              {plan.terms_sooner_than_standard ? ` · ${formatTerms(plan.terms_sooner_than_standard)} sooner` : ''}
            </p>
          </div>
        </header>

        <table className="mt-3 w-full">
          <thead className="text-left text-[0.7rem] uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="py-1 pr-2">Term</th>
              <th scope="col" className="py-1 pr-2">Courses</th>
              <th scope="col" className="py-1 text-right">Hrs</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {plan.credited.length > 0 && (
              <tr>
                <th scope="row" className="py-1 pr-2 text-left align-top font-semibold">Already earned</th>
                <td className="py-1 pr-2">
                  {plan.credited
                    .map((c) => `${c.code.startsWith('REQ:') ? c.counts_toward : c.code} (${SOURCE_LABEL[c.source] ?? c.source})`)
                    .join(', ')}
                </td>
                <td className="py-1 text-right">{formatHours(plan.credited.reduce((s, c) => s + c.hours, 0))}</td>
              </tr>
            )}
            {plan.terms.map((t) => (
              <tr key={t.id}>
                <th scope="row" className="py-1 pr-2 text-left align-top font-semibold whitespace-nowrap">{t.label}</th>
                <td className="py-1 pr-2">
                  {t.courses
                    .map((c) => `${c.label}${c.critical ? '*' : ''}${c.transfer ? ' (transfer)' : ''}${c.low_confidence ? ' (?)' : ''}`)
                    .join(', ')}
                </td>
                <td className="py-1 text-right align-top">{formatHours(t.hours)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-1 text-[0.7rem] text-muted">* critical (delaying it delays graduation) · (?) summer/winter offering not confirmed</p>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <section>
            <h3 className="text-base font-semibold">Levers used</h3>
            {leversUsed.length === 0 ? (
              <p className="text-muted">None: standard fall/spring pace.</p>
            ) : (
              <ul className="list-disc pl-5">
                {leversUsed.map((l) => (
                  <li key={l.id}>
                    {l.label}
                    {l.terms_saved ? ` — saves ${formatTerms(l.terms_saved)}` : ''}
                  </li>
                ))}
              </ul>
            )}
            {request.levers.planned_exams.length > 0 && (
              <p className="mt-1">Planned exams: {request.levers.planned_exams.join(', ')}</p>
            )}
          </section>
          <section>
            <h3 className="text-base font-semibold">Petitions & approvals needed</h3>
            {petitions.length === 0 ? (
              <p className="text-muted">None.</p>
            ) : (
              <ul className="list-disc pl-5">
                {petitions.map((p) => (
                  <li key={p.what}>
                    {p.what}: <strong>{p.who}</strong>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        {problems.length > 0 && (
          <section className="mt-4">
            <h3 className="text-base font-semibold">Things to check</h3>
            <ul className="list-disc pl-5">
              {problems.slice(0, 8).map((w) => (
                <li key={w.id}>{w.message}</li>
              ))}
            </ul>
          </section>
        )}

        <section className="mt-4">
          <h3 className="text-base font-semibold">Assumptions</h3>
          <ul className="list-disc pl-5 text-ink-soft">
            {plan.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>

        <footer className="mt-4 border-t border-line pt-2 text-[0.72rem] text-muted">
          <p className="font-semibold text-ink-soft">{DISCLAIMER}</p>
          <p className="break-all">Open this plan: {link}</p>
        </footer>
      </article>
    </div>
  )
}
