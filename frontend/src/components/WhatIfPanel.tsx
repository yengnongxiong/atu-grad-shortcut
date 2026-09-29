import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { PlanRequest, PlanResponse, ProgramListItem, WhatIfEvent, WhatIfResponse } from '../api/types'
import { formatTerms } from '../format'
import { ErrorBox, Spinner } from './ui'

type EventType = WhatIfEvent['type']

const LABELS: Record<EventType, string> = {
  fail: 'I fail a course',
  drop: 'I drop to fewer hours',
  skip: 'I skip a term',
  change_major: 'I change my major',
}

export function WhatIfPanel({
  plan,
  request,
  programs,
  initialCourse,
}: {
  plan: PlanResponse
  request: PlanRequest
  programs: ProgramListItem[]
  initialCourse?: string
}) {
  const courses = useMemo(
    () =>
      plan.terms.flatMap((t) =>
        t.courses.filter((c) => c.code).map((c) => ({ code: c.code as string, term: t.id, label: `${c.code} — ${t.label}`, critical: c.critical })),
      ),
    [plan],
  )
  const regularTerms = plan.terms
  const [type, setType] = useState<EventType>('fail')
  const [code, setCode] = useState(initialCourse ?? courses.find((c) => c.critical)?.code ?? courses[0]?.code ?? '')
  const [term, setTerm] = useState(regularTerms[1]?.id ?? regularTerms[0]?.id ?? '')
  const [hours, setHours] = useState(9)
  const [programId, setProgramId] = useState('')
  const [result, setResult] = useState<WhatIfResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const event = (): WhatIfEvent => {
    if (type === 'fail') return { type, code }
    if (type === 'drop') return { type, term, hours }
    if (type === 'skip') return { type, term }
    return { type, program_id: programId }
  }
  const ready = type === 'fail' ? Boolean(code) : type === 'change_major' ? Boolean(programId) : Boolean(term)

  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.whatIf(request, event()))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const later = result?.terms_later ?? 0
  return (
    <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
      <form
        className="card space-y-4 p-4"
        onSubmit={(e) => {
          e.preventDefault()
          void run()
        }}
      >
        <fieldset>
          <legend className="text-sm font-semibold">What if…</legend>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {(Object.keys(LABELS) as EventType[]).map((key) => (
              <label key={key} className={`cursor-pointer rounded-lg border px-2 py-2 text-sm ${type === key ? 'border-ink bg-paper-deep font-semibold' : 'border-line'}`}>
                <input type="radio" name="whatif-type" className="sr-only" checked={type === key} onChange={() => setType(key)} />
                {LABELS[key]}
              </label>
            ))}
          </div>
        </fieldset>
        {type === 'fail' && (
          <label className="block text-sm">
            <span className="font-semibold">Course</span>
            <select className="input mt-1" value={code} onChange={(e) => setCode(e.target.value)}>
              {courses.map((c) => (
                <option key={`${c.code}-${c.term}`} value={c.code}>
                  {c.critical ? '◆ ' : ''}
                  {c.label}
                </option>
              ))}
            </select>
          </label>
        )}
        {(type === 'drop' || type === 'skip') && (
          <label className="block text-sm">
            <span className="font-semibold">Term</span>
            <select className="input mt-1" value={term} onChange={(e) => setTerm(e.target.value)}>
              {regularTerms.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label} ({t.hours} hrs planned)
                </option>
              ))}
            </select>
          </label>
        )}
        {type === 'drop' && (
          <label className="block text-sm">
            <span className="font-semibold">Hours that term</span>
            <input type="number" min={0} max={18} className="input mt-1 w-24" value={hours} onChange={(e) => setHours(Number(e.target.value))} />
          </label>
        )}
        {type === 'change_major' && (
          <label className="block text-sm">
            <span className="font-semibold">New major</span>
            <select className="input mt-1" value={programId} onChange={(e) => setProgramId(e.target.value)}>
              <option value="">Choose…</option>
              {programs
                .filter((p) => p.id !== plan.program.id)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.listed_title} ({p.catalog_year})
                  </option>
                ))}
            </select>
          </label>
        )}
        <button type="submit" className="btn-primary w-full" disabled={!ready || busy}>
          {busy ? 'Re-solving…' : 'Run what-if'}
        </button>
        <p className="text-xs text-muted">Each what-if is a full re-solve from the affected term, not an estimate.</p>
      </form>
      <div aria-live="polite" className="space-y-4">
        {busy && <Spinner label="Re-solving your plan…" />}
        {error && <ErrorBox message={error} />}
        {!result && !busy && !error && (
          <p className="text-sm text-muted">Pick an event. Failing a course on the critical chain (◆) usually costs the most.</p>
        )}
        {result && (
          <>
            <div className={`rounded-xl border p-4 ${later > 0 ? 'border-critical/40 bg-critical-soft' : 'border-saved/40 bg-saved-soft'}`}>
              <p className="text-sm font-semibold uppercase tracking-wide text-muted">Graduation</p>
              <p className="mt-1 font-display text-2xl font-semibold">
                {result.before?.date_label ?? '—'} → <span className={later > 0 ? 'text-critical' : 'text-saved'}>{result.after?.date_label ?? 'no plan'}</span>
                {later !== 0 && <span className="ml-2 text-base">({formatTerms(Math.abs(later))} {later > 0 ? 'later' : 'sooner'})</span>}
              </p>
              <p className="mt-2 text-sm">{result.explanation}</p>
            </div>
            {result.changed_terms.length > 0 && (
              <div className="overflow-x-auto rounded-xl border border-line">
                <table className="w-full min-w-[36rem] text-sm">
                  <caption className="sr-only">Terms that changed</caption>
                  <thead className="bg-paper-deep text-left text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th scope="col" className="px-3 py-2">Term</th>
                      <th scope="col" className="px-3 py-2">Before</th>
                      <th scope="col" className="px-3 py-2">After</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line bg-surface">
                    {result.changed_terms.map((c) => (
                      <tr key={c.term}>
                        <th scope="row" className="px-3 py-2 text-left font-semibold">
                          {c.label}
                        </th>
                        <td className="px-3 py-2 text-muted">{c.before.join(', ') || '—'}</td>
                        <td className="px-3 py-2">{c.after.join(', ') || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
