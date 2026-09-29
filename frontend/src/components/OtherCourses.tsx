import { useState } from 'react'
import type { CompletedCourse, Grade } from '../api/types'

const GRADES: Grade[] = ['A', 'B', 'C', 'D', 'F', 'P']
const SOURCE_NAME: Record<CompletedCourse['source'], string> = { atu: 'ATU', transfer: 'transfer', exam: 'exam credit' }

export function OtherCourses({ others, onChange }: { others: CompletedCourse[]; onChange: (rows: CompletedCourse[]) => void }) {
  const [code, setCode] = useState('')
  const [grade, setGrade] = useState<Grade>('B')
  const [source, setSource] = useState<CompletedCourse['source']>('transfer')
  const valid = /^[A-Za-z]{2,5}\s?-?\d{4}$/.test(code.trim())
  const add = () => {
    if (!valid) return
    const normalized = code.trim().toUpperCase().replace(/[-\s]+/, ' ').replace(/^([A-Z]+)(\d)/, '$1 $2')
    const row: CompletedCourse = { code: normalized, grade: source === 'exam' ? 'P' : grade, source }
    onChange([...others.filter((o) => o.code !== normalized), row])
    setCode('')
  }
  return (
    <div>
      <h2 className="text-xl font-semibold">Gen-eds, electives & transfer credit</h2>
      <p className="text-sm text-muted">
        Enter by ATU-equivalent code (e.g. HIST 2003). Transfer, dual, and exam credit count toward total hours, not ATU residency. Exam credit also counts toward the exam-credit cap.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="text-sm">
          <span className="block font-semibold">Course code</span>
          <input aria-label="Course code" className="input mt-1 w-36" value={code} placeholder="HIST 2003" onChange={(e) => setCode(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && add()} />
        </label>
        <label className="text-sm">
          <span className="block font-semibold">Grade</span>
          <select className="input mt-1 w-20" value={grade} disabled={source === 'exam'} onChange={(e) => setGrade(e.target.value as Grade)}>
            {GRADES.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-semibold">Where</span>
          <select aria-label="Where" className="input mt-1 w-52" value={source} onChange={(e) => setSource(e.target.value as CompletedCourse['source'])}>
            <option value="transfer">Transfer / dual credit</option>
            <option value="atu">At ATU</option>
            <option value="exam">Credit by exam (AP/CLEP/IB, already posted)</option>
          </select>
        </label>
        <button type="button" className="btn-secondary" disabled={!valid} onClick={add}>
          Add course
        </button>
      </div>
      {others.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {others.map((o) => (
            <li key={o.code} className="flex items-center gap-2 rounded-md border border-line bg-paper px-2 py-1 text-sm">
              <span className="font-mono text-xs font-semibold">{o.code}</span>
              <span className="text-muted">{o.source === 'exam' ? `exam credit${o.exam ? ` (${o.exam})` : ''}` : `${o.grade} · ${SOURCE_NAME[o.source]}`}</span>
              <button type="button" className="text-muted hover:text-ink" aria-label={`Remove ${o.code}`} onClick={() => onChange(others.filter((x) => x.code !== o.code))}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
