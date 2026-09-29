import type { StudentProfile } from '../api/types'
import type { AuditImport } from '../degreeworks/types'

/**
 * The last imported audit, kept for this browser tab only (sessionStorage), so the plan page
 * can compare it with the plan. It holds course codes, grades, terms, and still-needed items;
 * the parser never reads the student's name or ID.
 */
const KEY = 'shortcut.audit.v1'

export interface StoredAudit {
  programId: string
  /** recordKey() of the imported profile: the comparison only applies to that record. */
  recordKey: string
  audit: AuditImport
}

/** A fingerprint of a profile's courses, independent of order. */
export function recordKey(profile: StudentProfile): string {
  const done = profile.completed.map((c) => `${c.code}:${c.grade}:${c.source}`).sort()
  return JSON.stringify([done, [...profile.in_progress].sort()])
}

/** The imported audit, if `profile` is still the imported record in the same program. */
export function auditFor(stored: StoredAudit | null, profile: StudentProfile): AuditImport | null {
  if (!stored || stored.programId !== profile.program_id || stored.recordKey !== recordKey(profile)) return null
  return stored.audit
}

export function saveAudit(value: StoredAudit | null): void {
  try {
    if (value) sessionStorage.setItem(KEY, JSON.stringify(value))
    else sessionStorage.removeItem(KEY)
  } catch {
    // storage unavailable (private mode, blocked): the comparison just won't survive a reload
  }
}

export function loadAudit(): StoredAudit | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredAudit
    return parsed && typeof parsed.recordKey === 'string' && Array.isArray(parsed.audit?.stillNeeded) ? parsed : null
  } catch {
    return null
  }
}
