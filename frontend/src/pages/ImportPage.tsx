import type { PlanRequest, ProgramListItem } from '../api/types'
import { AuditImport } from '../components/AuditImport'
import { Spinner } from '../components/ui'
import type { AuditImport as ParsedAudit } from '../degreeworks/types'

export function ImportPage({
  programs,
  loading,
  onApply,
}: {
  programs: ProgramListItem[]
  loading: boolean
  onApply: (request: PlanRequest, audit: ParsedAudit) => void
}) {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <p className="eyebrow">Start from Degree Works</p>
      <h1 className="mt-1 text-4xl font-semibold">Import your degree audit</h1>
      <p className="mt-3 text-ink-soft">
        Degree Works tells you what’s done and what’s left. Shortcut reads that record, then works out when to take what’s left, in what order, and
        how fast you could realistically finish.
      </p>
      <div className="card mt-6 p-5 sm:p-6">{loading ? <Spinner label="Loading majors…" /> : <AuditImport programs={programs} onApply={onApply} />}</div>
    </div>
  )
}
