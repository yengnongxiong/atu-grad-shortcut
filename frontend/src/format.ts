export function formatTerms(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const abs = Math.abs(value)
  const whole = Math.floor(abs + 1e-9)
  const half = abs - whole >= 0.49
  const text = `${whole === 0 && half ? '' : whole}${half ? '½' : ''}` || '0'
  const plural = abs === 1 ? 'term' : 'terms'
  return `${text} ${plural}`
}

export function formatHours(value: number): string {
  return Number.isInteger(value) ? `${value}` : value.toFixed(1)
}

export function pluralize(count: number, word: string, plural = `${word}s`): string {
  return `${count} ${count === 1 ? word : plural}`
}

export const TIER_LABEL: Record<string, string> = {
  cross_checked: 'Cross-checked',
  auto_imported: 'Auto-imported',
  needs_review: 'Needs review',
}

export const TIER_HELP: Record<string, string> = {
  cross_checked:
    'All validation checks passed and the parsed program was compared row by row against the rendered degree map and catalog data (review notes in the data report).',
  auto_imported: 'All automated validation checks passed.',
  needs_review: 'At least one validation check failed. Plans are a rough sketch; compare with the degree map.',
}

export const CONFIDENCE_LABEL: Record<string, string> = {
  documented: 'Documented',
  derived: 'Derived',
  assumed: 'Assumed',
  unknown: 'Unknown',
  conflicting: 'Conflicting sources',
}

export const SOURCE_LABEL: Record<string, string> = {
  atu: 'ATU',
  transfer: 'Transfer',
  exam: 'Exam credit',
  planned_exam: 'Planned exam',
  in_progress: 'In progress',
  assumed_pass: 'Completed',
}
