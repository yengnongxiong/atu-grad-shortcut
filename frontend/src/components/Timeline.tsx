import type { CreditedCourse, PlannedCourse, PlannedTerm } from '../api/types'
import { CONFIDENCE_LABEL, SOURCE_LABEL, formatHours } from '../format'
import { CriticalIcon } from './ui'

const SEASON_STYLE: Record<string, string> = {
  FA: 'border-t-[#9a6b2f]',
  SP: 'border-t-[#4d7a54]',
  SU: 'border-t-[#c28a17]',
  WI: 'border-t-[#44699a]',
}

function CourseChip({ course, onSelect }: { course: PlannedCourse; onSelect?: (course: PlannedCourse) => void }) {
  const tone = course.critical ? 'border-critical/60 bg-critical-soft' : 'border-line bg-surface'
  const details = [
    course.title !== course.label ? course.title : '',
    course.options.length ? `Options: ${course.options.slice(0, 6).join(', ')}${course.options.length > 6 ? '…' : ''}` : '',
    `Offering: ${CONFIDENCE_LABEL[course.offering_confidence] ?? course.offering_confidence}${course.offering_note ? ` — ${course.offering_note}` : ''}`,
    course.slack !== null ? `Prerequisite slack: ${course.slack} term${course.slack === 1 ? '' : 's'}` : '',
  ]
    .filter(Boolean)
    .join('\n')
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect?.(course)}
        title={details}
        className={`relative w-full rounded-lg border px-2.5 py-2 text-left text-sm transition-shadow hover:shadow-sm ${tone}`}
      >
        <span className="flex items-start justify-between gap-2">
          <span className="min-w-0">
            <span className={`flex items-center gap-1 font-semibold ${course.code ? 'font-mono text-[0.8rem]' : ''}`}>
              {course.critical && (
                <span className="text-critical" title="Critical: delaying it delays graduation">
                  <CriticalIcon />
                  <span className="sr-only">Critical.</span>
                </span>
              )}
              <span className="truncate">{course.label}</span>
            </span>
            {course.code && <span className="block truncate text-xs text-ink-soft">{course.title}</span>}
          </span>
          <span className="shrink-0 text-xs font-semibold text-muted">{formatHours(course.hours)}</span>
        </span>
        <span className="mt-1 flex flex-wrap gap-1">
          {course.transfer && <span className="chip border-info/40 bg-info-soft text-info">Transfer</span>}
          {course.kind === 'added_prereq' && <span className="chip border-line-strong bg-paper text-ink-soft">Added prereq</span>}
          {course.low_confidence && (
            <span className="chip border-warn/40 bg-warn-soft text-warn" title={course.offering_note}>
              ? Unconfirmed offering
            </span>
          )}
          {course.min_grade && <span className="chip border-line bg-paper text-muted">C or better</span>}
        </span>
      </button>
    </li>
  )
}

export function Timeline({
  terms,
  credited,
  onSelectCourse,
}: {
  terms: PlannedTerm[]
  credited: CreditedCourse[]
  onSelectCourse?: (course: PlannedCourse) => void
}) {
  return (
    <div className="relative overflow-x-auto pb-2" tabIndex={0} aria-label="Term-by-term plan (scrolls horizontally)">
      <ol className="flex min-w-max gap-3">
        {credited.length > 0 && (
          <li className="w-56 shrink-0">
            <div className="rounded-xl border border-dashed border-line-strong bg-paper-deep p-3">
              <p className="eyebrow">Already earned</p>
              <p className="font-display text-lg font-semibold">
                {formatHours(credited.reduce((sum, c) => sum + c.hours, 0))} hrs
              </p>
              <ul className="mt-2 space-y-1.5 text-sm">
                {credited.map((c) => (
                  <li key={`${c.code}-${c.requirement_id ?? 'x'}`} className="rounded-md border border-line bg-surface px-2 py-1.5">
                    <span className="font-mono text-[0.78rem] font-semibold">{c.code.startsWith('REQ:') ? c.counts_toward : c.code}</span>{' '}
                    <span className="chip ml-1 border-saved/40 bg-saved-soft text-saved">{SOURCE_LABEL[c.source] ?? c.source}</span>
                    <span className="block truncate text-xs text-muted">→ {c.counts_toward}</span>
                  </li>
                ))}
              </ul>
            </div>
          </li>
        )}
        {terms.map((term) => (
          <li key={term.id} className="w-60 shrink-0">
            <section
              aria-label={`${term.label}: ${formatHours(term.hours)} hours`}
              className={`card h-full border-t-4 p-3 ${SEASON_STYLE[term.season] ?? ''} ${term.season === 'SU' || term.season === 'WI' ? 'bg-[#fffdf7]' : ''}`}
            >
              <header className="flex items-baseline justify-between gap-2">
                <h3 className="font-display text-lg font-semibold">{term.label}</h3>
                <span className={`text-sm font-semibold ${term.overload ? 'text-critical' : 'text-ink-soft'}`}>
                  {formatHours(term.hours)} hrs
                </span>
              </header>
              <p className="text-xs text-muted">
                ~{Math.round(term.workload_low)}–{Math.round(term.workload_high)} hrs/week incl. study
              </p>
              {term.approval && (
                <p className="mt-1 rounded bg-critical-soft px-2 py-0.5 text-xs font-semibold text-critical">{term.approval}</p>
              )}
              {term.courses.length === 0 ? (
                <p className="mt-3 text-sm text-muted">No courses this term.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {term.courses.map((course) => (
                    <CourseChip key={course.item_id} course={course} onSelect={onSelectCourse} />
                  ))}
                </ul>
              )}
            </section>
          </li>
        ))}
      </ol>
    </div>
  )
}
