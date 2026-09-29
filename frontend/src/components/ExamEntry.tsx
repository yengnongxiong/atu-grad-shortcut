import { useMemo, useState } from 'react'
import type { ExamScore, ExamTable, StudentProfile } from '../api/types'

const PROGRAMS: ExamScore['program'][] = ['CLEP', 'AP', 'IB']
const SCORE_RANGE: Record<ExamScore['program'], [number, number]> = { CLEP: [20, 80], AP: [1, 5], IB: [1, 7] }

const sameExam = (a: ExamScore, program: string, exam: string) => a.program === program && a.exam === exam

export function ExamEntry({ profile, exams, update }: { profile: StudentProfile; exams: ExamTable[]; update: (patch: Partial<StudentProfile>) => void }) {
  const [program, setProgram] = useState<ExamScore['program']>('CLEP')
  const [exam, setExam] = useState('')
  const [score, setScore] = useState('')
  const table = exams.find((t) => t.program === program)
  const names = useMemo(() => [...new Set(table?.equivalencies.map((e) => e.exam) ?? [])].sort(), [table])
  const tiers = table?.equivalencies.filter((e) => e.exam === exam) ?? []
  const [low, high] = SCORE_RANGE[program]
  const add = () => {
    if (!exam || !score) return
    const rest = profile.exams.filter((e) => !sameExam(e, program, exam))
    update({ exams: [...rest, { program, exam, score: Number(score) }] })
    setExam('')
    setScore('')
  }
  return (
    <div>
      <h2 className="text-xl font-semibold">Exam scores</h2>
      <p className="text-sm text-muted">
        Scores map through the AP, CLEP, and IB tables in ATU’s catalog. If the credit is already on your record (Degree Works shows “CE”), add the
        course above as “Credit by exam” instead.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="text-sm">
          <span className="block font-semibold">Program</span>
          <select
            aria-label="Program"
            className="input mt-1 w-24"
            value={program}
            onChange={(e) => {
              setProgram(e.target.value as ExamScore['program'])
              setExam('')
            }}
          >
            {PROGRAMS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-semibold">Exam</span>
          <select aria-label="Exam" className="input mt-1 w-72" value={exam} onChange={(e) => setExam(e.target.value)}>
            <option value="">Choose an exam…</option>
            {names.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-semibold">Score</span>
          <input aria-label="Score" type="number" min={low} max={high} className="input mt-1 w-24" value={score} onChange={(e) => setScore(e.target.value)} />
        </label>
        <button type="button" className="btn-secondary" disabled={!exam || !score} onClick={add}>
          Add exam
        </button>
      </div>
      {tiers.length > 0 && (
        <p className="mt-2 text-xs text-muted">
          {tiers
            .map((t) => {
              const courses = t.awards.map((a) => a.join(' & ')).join(' or ')
              const credit = [courses, t.generic_credit].filter(Boolean).join(' + ')
              return `${t.min_score}+ → ${credit}`
            })
            .join(' · ')}
          {tiers.some((t) => t.generic_credit) && '. Generic credit isn’t placed on a requirement; ask your advisor where it applies.'}
        </p>
      )}
      {profile.exams.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {profile.exams.map((e) => (
            <li key={`${e.program}-${e.exam}`} className="flex items-center gap-2 rounded-md border border-line px-2 py-1 text-sm">
              <span className="font-semibold">{e.program}</span> {e.exam}: {e.score}
              <button
                type="button"
                className="text-muted hover:text-ink"
                aria-label={`Remove ${e.program} ${e.exam}`}
                onClick={() => update({ exams: profile.exams.filter((x) => !sameExam(x, e.program, e.exam)) })}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
