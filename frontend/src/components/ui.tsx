import type { ReactNode } from 'react'
import { policyNumber, type Policies } from '../api/policies'
import type { TrustTier } from '../api/types'
import { TIER_HELP, TIER_LABEL } from '../format'

/** "Critical" said in a word, not an icon or a color. */
export function CriticalTag({ className = '' }: { className?: string }) {
  return <span className={`inline-block rounded border border-ink px-1 text-[0.65rem] font-semibold uppercase leading-4 tracking-wide text-ink ${className}`}>Critical</span>
}

export function TrustBadge({ tier, compact = false }: { tier: TrustTier; compact?: boolean }) {
  return (
    <span className={`chip ${tier === 'needs_review' ? 'border-ink text-ink' : ''}`} title={TIER_HELP[tier]}>
      {compact ? TIER_LABEL[tier] : `${TIER_LABEL[tier]} data`}
    </span>
  )
}

export function Tag({ children, tone = 'neutral', title }: { children: ReactNode; tone?: 'neutral' | 'critical' | 'saved' | 'warn' | 'info'; title?: string }) {
  const styles = {
    neutral: '',
    critical: 'border-ink font-semibold text-ink',
    saved: 'border-ink font-semibold text-ink',
    warn: 'border-ink text-ink',
    info: '',
  }
  return (
    <span className={`chip ${styles[tone]}`} title={title}>
      {children}
    </span>
  )
}

export function Spinner({ label = 'Working…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 text-sm text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-ink" aria-hidden="true" />
      {label}
    </div>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-md border border-error/40 bg-error-soft p-4 text-sm text-error">
      <p className="font-semibold">Something went wrong</p>
      <p className="mt-1">{message}</p>
      {onRetry && (
        <button type="button" className="btn-secondary mt-3" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function Section({ title, eyebrow, children, actions }: { title: string; eyebrow?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="card p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h2 className="text-xl font-semibold">{title}</h2>
        </div>
        {actions}
      </div>
      {children}
    </section>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled = false,
  describedBy,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  label: string
  disabled?: boolean
  describedBy?: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      aria-describedby={describedBy}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
        checked ? 'border-ink bg-ink' : 'border-line-strong bg-paper-deep'
      }`}
    >
      <span
        aria-hidden="true"
        className={`inline-block h-4 w-4 transform rounded-full bg-surface transition-transform ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  )
}

/** A policy number, linked to its source on the About page (CLAUDE.md UI rules). */
export function PolicyLink({ policies, name, format = String }: { policies: Policies | null; name: string; format?: (value: number) => string }) {
  const value = policyNumber(policies, name)
  if (value === null) return <span aria-busy="true">…</span>
  return <a href={`/about#policy-${name}`}>{format(value)}</a>
}
