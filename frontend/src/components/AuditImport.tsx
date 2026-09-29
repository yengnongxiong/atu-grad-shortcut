import { useState } from 'react'
import { loadPolicies, policyNumber } from '../api/policies'
import type { PlanRequest, ProgramListItem } from '../api/types'
import { readPdfLines } from '../degreeworks/pdfLines'
import { parseAudit } from '../degreeworks/parse'
import { auditToProfile, type ProfileImport } from '../degreeworks/toProfile'
import type { AuditImport as ParsedAudit } from '../degreeworks/types'
import { pluralize } from '../format'
import { defaultLevers, termLabel } from '../state/profile'
import { ProgramPicker } from './ProgramPicker'
import { ErrorBox, Spinner } from './ui'

type Stage = { kind: 'idle' } | { kind: 'reading' } | { kind: 'error'; message: string } | { kind: 'review'; audit: ParsedAudit; result: ProfileImport }

export const PRIVACY_NOTE =
  'Your audit is read on this device and never uploaded. Shortcut keeps only course codes, grades, and terms; your name and student ID aren’t saved or sent.'

export function AuditImport({ programs, onApply }: { programs: ProgramListItem[]; onApply: (request: PlanRequest, audit: ParsedAudit) => void }) {
  const [stage, setStage] = useState<Stage>({ kind: 'idle' })
  const [programId, setProgramId] = useState('')

  const read = async (file: File | undefined) => {
    if (!file) return
    setStage({ kind: 'reading' })
    try {
      const [lines, policies] = await Promise.all([readPdfLines(file), loadPolicies()])
      const audit = parseAudit(lines)
      if (!audit.degree && audit.courses.length === 0) {
        setStage({
          kind: 'error',
          message: 'This file doesn’t look like a Degree Works audit. In Degree Works, open your audit, save it as a PDF, and choose that file.',
        })
        return
      }
      const result = auditToProfile(audit, programs, policyNumber(policies, 'overload_gpa_min') ?? Number.POSITIVE_INFINITY)
      setProgramId(result.profile.program_id)
      setStage({ kind: 'review', audit, result })
    } catch (err) {
      setStage({ kind: 'error', message: `Couldn’t read that PDF (${err instanceof Error ? err.message : String(err)}).` })
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-ink-soft">{PRIVACY_NOTE}</p>
      <label className="block text-sm">
        <span className="font-semibold">Degree Works audit (PDF)</span>
        <input
          type="file"
          accept="application/pdf,.pdf"
          className="mt-1 block w-full text-sm file:mr-3 file:rounded-md file:border file:border-line-strong file:bg-surface file:px-3 file:py-1.5 file:text-sm"
          onChange={(e) => void read(e.target.files?.[0])}
        />
        <span className="mt-1 block text-xs text-muted">In Degree Works, open your audit and save it as a PDF.</span>
      </label>
      {stage.kind === 'reading' && <Spinner label="Reading your audit…" />}
      {stage.kind === 'error' && <ErrorBox message={stage.message} />}
      {stage.kind === 'review' && <Review stage={stage} programs={programs} programId={programId} setProgramId={setProgramId} onApply={onApply} />}
    </div>
  )
}

function Review({
  stage,
  programs,
  programId,
  setProgramId,
  onApply,
}: {
  stage: Extract<Stage, { kind: 'review' }>
  programs: ProgramListItem[]
  programId: string
  setProgramId: (id: string) => void
  onApply: (request: PlanRequest, audit: ParsedAudit) => void
}) {
  const { audit, result } = stage
  const profile = { ...result.profile, program_id: programId }
  const program = programs.find((p) => p.id === programId)
  const count = (source: string) => profile.completed.filter((c) => c.source === source).length
  const notUsed = audit.courses.filter((c) => c.section === 'not_used').length
  return (
    <section className="card space-y-4 p-4" aria-label="What Shortcut read from your audit">
      <h2 className="text-lg font-semibold">What Shortcut read</h2>
      {program ? (
        <p className="text-sm">{`${program.listed_title} · ${program.catalog_year} catalog`}</p>
      ) : (
        <div className="space-y-2">
          <p className="text-sm">Shortcut couldn’t match “{audit.degree ?? 'your degree'}” to a major it has. Pick yours:</p>
          <ProgramPicker programs={programs} value={programId} preferredYear={audit.catalogYear ?? undefined} onSelect={(p) => setProgramId(p.id)} />
        </div>
      )}
      <ul className="grid gap-1 text-sm sm:grid-cols-2">
        <li>{`${String(count('atu'))} completed at ATU`}</li>
        <li>{`${String(count('exam'))} by exam`}</li>
        <li>{`${String(count('transfer'))} transfer`}</li>
        <li>{`${String(profile.in_progress.length)} in progress`}</li>
        {notUsed > 0 && <li>{notUsed === 1 ? '1 not applied to your degree (it still counts toward hours)' : `${String(notUsed)} not applied to your degree (they still count toward hours)`}</li>}
        {audit.creditsApplied !== null && <li>{`${pluralize(audit.creditsApplied, 'credit')} applied, per Degree Works`}</li>}
      </ul>
      <p className="text-sm text-muted">
        First term at ATU: {termLabel(profile.first_term)} · planning from {termLabel(profile.plan_from ?? profile.first_term)}
      </p>
      {result.notes.filter((n) => !n.startsWith('Shortcut couldn’t match')).length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm text-ink-soft">
          {result.notes
            .filter((n) => !n.startsWith('Shortcut couldn’t match'))
            .map((note) => (
              <li key={note}>{note}</li>
            ))}
        </ul>
      )}
      {audit.unrecognized.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer">{`${pluralize(audit.unrecognized.length, 'line')} Shortcut couldn’t read`}</summary>
          <ul className="mt-1 space-y-1 font-mono text-xs">
            {audit.unrecognized.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </details>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-primary" disabled={!programId} onClick={() => onApply({ profile, levers: defaultLevers() }, audit)}>
          Use this record
        </button>
      </div>
      <p className="text-xs text-muted">You can edit anything afterward in Setup.</p>
    </section>
  )
}
