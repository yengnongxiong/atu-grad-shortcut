import type { AuditImport } from '../degreeworks/types'

/**
 * The last imported audit, kept for this browser tab only (sessionStorage), so the plan page
 * can compare it with the plan. It holds course codes, grades, terms, and still-needed items;
 * the parser never reads the student's name or ID.
 */
const KEY = 'shortcut.audit.v1'

export interface StoredAudit {
  programId: string
  audit: AuditImport
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
    return parsed && typeof parsed.programId === 'string' && Array.isArray(parsed.audit?.stillNeeded) ? parsed : null
  } catch {
    return null
  }
}
