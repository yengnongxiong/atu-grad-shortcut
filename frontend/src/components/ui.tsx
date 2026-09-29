import type { ReactNode } from 'react'
import type { TrustTier } from '../api/types'
import { TIER_HELP, TIER_LABEL } from '../format'

export function CriticalIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 12 12" aria-hidden="true" className={`inline-block h-3 w-3 ${className}`}>
      <path d="M6 0.8 L11.2 6 L6 11.2 L0.8 6 Z" fill="currentColor" />
    </svg>
  )
}

export function ArrowIcon({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" className={`inline-block h-4 w-4 ${className}`}>
      <path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function TrustBadge({ tier, compact = false }: { tier: TrustTier; compact?: boolean }) {
  const styles: Record<TrustTier, string> = {
    cross_checked: 'border-saved/40 bg-saved-soft text-saved',
    auto_imported: 'border-info/30 bg-info-soft text-info',
    needs_review: 'border-warn/40 bg-warn-soft text-warn',
  }
  const glyph: Record<TrustTier, string> = { cross_checked: '✓✓', auto_imported: '✓', needs_review: '!' }
  return (
    <span className={`chip ${styles[tier]}`} title={TIER_HELP[tier]}>
      <span aria-hidden="true">{glyph[tier]}</span>
      {compact ? TIER_LABEL[tier] : `${TIER_LABEL[tier]} data`}
    </span>
  )
}

export function Tag({ children, tone = 'neutral', title }: { children: ReactNode; tone?: 'neutral' | 'critical' | 'saved' | 'warn' | 'info'; title?: string }) {
  const styles = {
    neutral: 'border-line-strong bg-paper text-ink-soft',
    critical: 'border-critical/40 bg-critical-soft text-critical',
    saved: 'border-saved/40 bg-saved-soft text-saved',
    warn: 'border-warn/40 bg-warn-soft text-warn',
    info: 'border-info/30 bg-info-soft text-info',
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
    <div role="alert" className="rounded-lg border border-error/40 bg-error-soft p-4 text-sm text-error">
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
        checked ? 'border-saved bg-saved' : 'border-line-strong bg-paper-deep'
      }`}
    >
      <span
        aria-hidden="true"
        className={`inline-block h-4 w-4 transform rounded-full bg-surface shadow transition-transform ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  )
}
