import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type {
  ExamTable,
  Grade,
  PlanRequest,
  ProgramDetail,
  ProgramListItem,
  StudentProfile,
} from '../api/types'
import { catalogYearFor, versionFor, versionsOf } from '../catalogYear'
import { ExamEntry } from '../components/ExamEntry'
import { OtherCourses } from '../components/OtherCourses'
import { ProgramPicker } from '../components/ProgramPicker'
import { ErrorBox, Spinner, TrustBadge } from '../components/ui'
import { navigate } from '../router'
import { defaultRequest, termOptions } from '../state/profile'

const GRADES: Grade[] = ['A', 'B', 'C', 'D', 'F', 'P']
const STEPS = ['Major & terms', 'Credit you have', 'Preferences'] as const

type CourseStatus = 'none' | 'done' | 'in_progress'

export function Setup({
  request,
  programs,
  onChange,
  onBuild,
}: {
  request: PlanRequest | null
  programs: ProgramListItem[]
  onChange: (request: PlanRequest) => void
  onBuild: (request: PlanRequest) => void
}) {
  const [step, setStep] = useState(0)
  const current = request ?? defaultRequest()
  const profile = current.profile
  const [detail, setDetail] = useState<ProgramDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [exams, setExams] = useState<ExamTable[]>([])

  useEffect(() => {
    if (!profile.program_id) return
    let cancelled = false
    api
      .program(profile.program_id)
      .then((d) => {
        if (!cancelled) {
          setDetail(d)
          setDetailError(null)
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) setDetailError(error instanceof Error ? error.message : String(error))
      })
    return () => {
      cancelled = true
    }
  }, [profile.program_id])

  useEffect(() => {
    api
      .exams()
      .then((r) => setExams(r.tables))
      .catch(() => setExams([]))
  }, [])

  const update = (patch: Partial<StudentProfile>) => onChange({ ...current, profile: { ...profile, ...patch } })
  const canContinue = step > 0 || Boolean(profile.program_id)

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <p className="eyebrow">Setup</p>
      <h1 className="mt-1 text-4xl font-semibold">Tell Shortcut where you are now</h1>
      <p className="mt-2 text-sm text-ink-soft">
        Have your Degree Works audit?{' '}
        <a
          href="/import"
          onClick={(event) => {
            event.preventDefault()
            navigate('import')
          }}
        >
          Import it instead
        </a>{' '}
        and skip typing your courses.
      </p>
      <ol className="mt-6 flex flex-wrap gap-2" aria-label="Setup steps">
        {STEPS.map((label, index) => (
          <li key={label}>
            <button
              type="button"
              onClick={() => (index === 0 || profile.program_id ? setStep(index) : undefined)}
              aria-current={index === step ? 'step' : undefined}
              className={`rounded-md border px-3 py-1 text-sm font-medium ${
                index === step ? 'border-ink bg-ink text-paper' : 'border-line-strong bg-surface text-ink-soft'
              }`}
            >
              {index + 1}. {label}
            </button>
          </li>
        ))}
      </ol>

      <div className="card mt-6 p-5 sm:p-7">
        {step === 0 && <StepMajor profile={profile} programs={programs} detail={detail} update={update} />}
        {step === 1 && (
          <StepCredit profile={profile} detail={detail} detailError={detailError} exams={exams} update={update} />
        )}
        {step === 2 && <StepPreferences profile={profile} update={update} />}
      </div>

      <div className="mt-6 flex items-center justify-between">
        <button type="button" className="btn-ghost" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
          Back
        </button>
        {step < STEPS.length - 1 ? (
          <button type="button" className="btn-primary" disabled={!canContinue} onClick={() => setStep((s) => s + 1)}>
            Continue
          </button>
        ) : (
          <button type="button" className="btn-primary" disabled={!profile.program_id} onClick={() => onBuild(current)}>
            Build my plan
          </button>
        )}
      </div>
      {step === 0 && profile.program_id && (
        <p className="mt-3 text-right text-sm text-muted">
          In a hurry?{' '}
          <button type="button" className="font-semibold underline" onClick={() => onBuild(current)}>
            Build a plan with no prior credit
          </button>
        </p>
      )}
    </div>
  )
}

export function StepMajor({
  profile,
  programs,
  detail,
  update,
}: {
  profile: StudentProfile
  programs: ProgramListItem[]
  detail: ProgramDetail | null
  update: (patch: Partial<StudentProfile>) => void
}) {
  const terms = useMemo(() => termOptions(2023, 2030), [])
  const selected = programs.find((p) => p.id === profile.program_id)
  const versions = versionsOf(programs, profile.program_id)
  const entryYear = catalogYearFor(profile.first_term)
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Major</h2>
        {selected && (
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-soft">
            <strong>{selected.listed_title}</strong> · {selected.catalog_year} catalog · {selected.college}
            <TrustBadge tier={selected.trust_tier} compact />
          </p>
        )}
        <div className="mt-3">
          <ProgramPicker
            programs={programs}
            value={profile.program_id}
            preferredYear={entryYear}
            onSelect={(p) => update({ program_id: p.id, completed: [], in_progress: [] })}
          />
        </div>
      </div>
      {versions.length > 1 && (
        <label className="block text-sm">
          <span className="font-semibold">Catalog year</span>
          <select aria-label="Catalog year" className="input mt-1 max-w-xs" value={profile.program_id} onChange={(e) => update({ program_id: e.target.value })}>
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                {v.catalog_year} degree map{v.catalog_year === entryYear ? ' (the year you started)' : ''}
              </option>
            ))}
          </select>
          <span className="mt-1 block text-xs text-muted">
            Use the map for the year you started. Your catalog year is on your Degree Works audit. ATU lets you graduate under that catalog or any
            later one, with your department head’s and dean’s approval.
          </span>
        </label>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="font-semibold">First term at ATU</span>
          <select
            aria-label="First term at ATU"
            className="input mt-1"
            value={profile.first_term}
            onChange={(e) =>
              update({ first_term: e.target.value, program_id: versionFor(programs, profile.program_id, catalogYearFor(e.target.value)) })
            }
          >
            {terms.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="font-semibold">Plan starting from</span>
          <select
            className="input mt-1"
            value={profile.plan_from ?? profile.first_term}
            onChange={(e) => update({ plan_from: e.target.value === profile.first_term ? null : e.target.value })}
          >
            {terms
              .filter((t) => t.id >= profile.first_term.slice(0, 4))
              .map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
          </select>
          <span className="mt-1 block text-xs text-muted">Usually your next term. Earlier terms count as history.</span>
        </label>
      </div>
      {detail && (
        <p className="text-sm text-muted">
          {detail.total_hours_min} hours · {detail.upper_level_hours_min} upper-division · minimum GPA {detail.gpa_min.toFixed(2)}
        </p>
      )}
    </div>
  )
}

function StepCredit({
  profile,
  detail,
  detailError,
  exams,
  update,
}: {
  profile: StudentProfile
  detail: ProgramDetail | null
  detailError: string | null
  exams: ExamTable[]
  update: (patch: Partial<StudentProfile>) => void
}) {
  const courseReqs = useMemo(() => {
    if (!detail) return []
    const seen = new Set<string>()
    const rows: { code: string; title: string; semester: number; minGrade: string | null }[] = []
    for (const req of detail.requirements) {
      if (req.kind !== 'course') continue
      for (const option of req.options) {
        for (const code of option) {
          if (seen.has(code)) continue
          seen.add(code)
          rows.push({ code, title: detail.courses[code]?.title ?? req.label, semester: req.map_semester, minGrade: req.min_grade })
        }
      }
    }
    return rows.sort((a, b) => a.semester - b.semester || a.code.localeCompare(b.code))
  }, [detail])

  const statusOf = (code: string): CourseStatus => {
    if (profile.in_progress.includes(code)) return 'in_progress'
    return profile.completed.some((c) => c.code === code) ? 'done' : 'none'
  }
  const setStatus = (code: string, status: CourseStatus) => {
    const completed = profile.completed.filter((c) => c.code !== code)
    const inProgress = profile.in_progress.filter((c) => c !== code)
    if (status === 'done') completed.push({ code, grade: 'C', source: 'atu' })
    if (status === 'in_progress') inProgress.push(code)
    update({ completed, in_progress: inProgress })
  }
  const setGrade = (code: string, grade: Grade) =>
    update({ completed: profile.completed.map((c) => (c.code === code ? { ...c, grade } : c)) })

  const programCodes = new Set(courseReqs.map((r) => r.code))
  const others = profile.completed.filter((c) => !programCodes.has(c.code))

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold">Math ACT</h2>
        <p className="text-sm text-muted">Used for math placement (e.g. Calculus I needs above 26 on the CS map).</p>
        <input
          type="number"
          min={1}
          max={36}
          inputMode="numeric"
          className="input mt-2 max-w-32"
          aria-label="Math ACT subscore"
          value={profile.math_act ?? ''}
          onChange={(e) => update({ math_act: e.target.value ? Math.max(1, Math.min(36, Number(e.target.value))) : null })}
        />
      </div>

      <div>
        <h2 className="text-xl font-semibold">Program courses</h2>
        <p className="text-sm text-muted">Mark what you’ve finished (with the grade) or are taking now. Default grade is “C or better”.</p>
        {detailError && <ErrorBox message={detailError} />}
        {!detail && !detailError && <Spinner label="Loading the program…" />}
        {detail && (
          <div className="mt-3 max-h-[26rem] overflow-y-auto rounded-md border border-line">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-paper-deep text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-3 py-2">Course</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Grade</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {courseReqs.map((row) => {
                  const status = statusOf(row.code)
                  const grade = profile.completed.find((c) => c.code === row.code)?.grade ?? 'C'
                  return (
                    <tr key={row.code}>
                      <td className="px-3 py-2">
                        <span className="font-mono text-xs font-semibold">{row.code}</span>{' '}
                        <span className="text-ink-soft">{row.title}</span>
                        {row.minGrade && <span className="ml-1 text-xs text-muted">(C or better)</span>}
                      </td>
                      <td className="px-3 py-2">
                        <select
                          aria-label={`${row.code} status`}
                          className="input py-1"
                          value={status}
                          onChange={(e) => setStatus(row.code, e.target.value as CourseStatus)}
                        >
                          <option value="none">Not yet</option>
                          <option value="done">Completed</option>
                          <option value="in_progress">In progress</option>
                        </select>
                      </td>
                      <td className="px-3 py-2">
                        <select
                          aria-label={`${row.code} grade`}
                          className="input py-1"
                          disabled={status !== 'done'}
                          value={grade}
                          onChange={(e) => setGrade(row.code, e.target.value as Grade)}
                        >
                          {GRADES.map((g) => (
                            <option key={g}>{g}</option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <OtherCourses others={others} onChange={(rows) => update({ completed: [...profile.completed.filter((c) => programCodes.has(c.code)), ...rows] })} />
      <ExamEntry profile={profile} exams={exams} update={update} />
    </div>
  )
}

function StepPreferences({ profile, update }: { profile: StudentProfile; update: (patch: Partial<StudentProfile>) => void }) {
  const prefs = profile.preferences
  const setPrefs = (patch: Partial<StudentProfile['preferences']>) => update({ preferences: { ...prefs, ...patch } })
  return (
    <div className="space-y-6">
      <label className="block text-sm">
        <span className="font-semibold">Preferred maximum hours per fall/spring term</span>
        <select
          className="input mt-1 max-w-48"
          value={prefs.preferred_hours ?? ''}
          onChange={(e) => setPrefs({ preferred_hours: e.target.value ? Number(e.target.value) : null })}
        >
          <option value="">16 (default)</option>
          {[12, 13, 14, 15, 16, 17, 18].map((h) => (
            <option key={h} value={h}>
              {h}
            </option>
          ))}
        </select>
        <span className="mt-1 block text-xs text-muted">This defines “standard pace”. Heavier terms and overloads are separate levers on the plan.</span>
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="font-semibold">Last-term GPA (optional)</span>
          <input
            type="number"
            step="0.01"
            min={0}
            max={4}
            className="input mt-1"
            value={prefs.last_term_gpa ?? ''}
            onChange={(e) => setPrefs({ last_term_gpa: e.target.value ? Math.max(0, Math.min(4, Number(e.target.value))) : null })}
          />
        </label>
        <label className="mt-6 flex items-start gap-3 text-sm">
          <input type="checkbox" className="mt-1 h-4 w-4" checked={prefs.expect_high_gpa} onChange={(e) => setPrefs({ expect_high_gpa: e.target.checked })} />
          <span>
            <span className="font-semibold">I expect to keep a 3.25+ GPA</span>
            <span className="block text-xs text-muted">Needed for overloads (19+ hours), which also need a dean’s petition.</span>
          </span>
        </label>
      </div>
      <fieldset>
        <legend className="text-sm font-semibold">Summer & winter availability</legend>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          {(['conservative', 'optimistic'] as const).map((mode) => (
            <label key={mode} className={`card flex cursor-pointer items-start gap-3 p-3 text-sm ${prefs.mode === mode ? 'outline outline-2 outline-ink' : ''}`}>
              <input type="radio" name="mode" className="mt-1" checked={prefs.mode === mode} onChange={() => setPrefs({ mode })} />
              <span>
                <span className="font-semibold capitalize">{mode}</span>
                <span className="block text-xs text-muted">
                  {mode === 'conservative'
                    ? 'Only schedules summer/winter courses the catalog, a degree map, or recent schedules support.'
                    : 'Also allows courses with unknown summer/winter availability, and flags each one.'}
                </span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  )
}
