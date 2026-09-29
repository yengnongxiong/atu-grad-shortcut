import { api } from '../api/client'
import type { ExamOpportunitiesResponse, PlanRequest } from '../api/types'
import { formatHours, formatTerms } from '../format'
import { useFetch } from '../state/usePlan'
import { ErrorBox, Spinner, Tag, Toggle } from './ui'

export function ExamOpportunities({
  request,
  onTogglePlanned,
}: {
  request: PlanRequest
  onTogglePlanned: (examId: string, value: boolean) => void
}) {
  const planned = new Set(request.levers.planned_exams)
  // Opportunities are computed against the plan without the exams chosen here.
  const baseKey = JSON.stringify({ ...request, levers: { ...request.levers, planned_exams: [] } })
  const { data, loading, error } = useFetch<ExamOpportunitiesResponse>(baseKey, (key) =>
    api.examOpportunities(JSON.parse(key) as PlanRequest),
  )

  if (error) return <ErrorBox message={error} />
  if (!data) return <Spinner label="Checking every ATU-accepted exam against what you still need…" />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <p className="max-w-3xl text-ink-soft">{data.note}</p>
        <Tag tone={data.exam_hours_used >= data.exam_cap_hours ? 'warn' : 'neutral'} title="Exam-credit cap (stricter of two ATU rules)">
          Exam credit used: {formatHours(data.exam_hours_used)} / {data.exam_cap_hours} hrs
        </Tag>
      </div>
      {loading && <Spinner label="Updating…" />}
      {data.opportunities.length === 0 ? (
        <p className="text-sm text-muted">No accepted exam maps to a requirement you still need.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[46rem] text-sm">
            <caption className="sr-only">Exam opportunities ranked by terms saved, then hours saved</caption>
            <thead className="bg-paper-deep text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th scope="col" className="px-3 py-2">Exam</th>
                <th scope="col" className="px-3 py-2">Score</th>
                <th scope="col" className="px-3 py-2">Awards</th>
                <th scope="col" className="px-3 py-2">Satisfies</th>
                <th scope="col" className="px-3 py-2 text-right">Hours</th>
                <th scope="col" className="px-3 py-2 text-right">Terms saved</th>
                <th scope="col" className="px-3 py-2">Add to plan</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {data.opportunities.map((o) => (
                <tr key={o.id}>
                  <td className="px-3 py-2">
                    <span className="chip mr-1 border-line-strong bg-paper text-ink-soft">{o.program}</span>
                    {o.source.url ? (
                      <a href={o.source.url} target="_blank" rel="noreferrer">
                        {o.exam}
                      </a>
                    ) : (
                      o.exam
                    )}
                  </td>
                  <td className="px-3 py-2">{o.min_score}+</td>
                  <td className="px-3 py-2 font-mono text-xs">{o.awards.join(', ')}</td>
                  <td className="px-3 py-2">{o.requirements_satisfied.join('; ')}</td>
                  <td className="px-3 py-2 text-right">{formatHours(o.hours_saved)}</td>
                  <td className="px-3 py-2 text-right font-semibold">
                    {o.exceeds_cap ? (
                      <span className="text-warn" title={o.cap_note}>
                        Over cap
                      </span>
                    ) : o.terms_saved && o.terms_saved > 0 ? (
                      <span className="text-saved">{formatTerms(o.terms_saved)}</span>
                    ) : (
                      <span className="text-muted">0</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <Toggle
                      checked={planned.has(o.id)}
                      disabled={o.exceeds_cap && !planned.has(o.id)}
                      label={`Plan to take ${o.exam}`}
                      onChange={(value) => onTogglePlanned(o.id, value)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-muted">
        Exam credit doesn’t count toward GPA, so it can’t help keep a scholarship. No duplicate credit for a course you already
        have a grade in.
      </p>
    </div>
  )
}
