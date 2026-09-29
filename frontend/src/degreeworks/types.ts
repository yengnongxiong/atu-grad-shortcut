/** What Shortcut reads from a Degree Works audit. Never holds the student's name or ID. */
export interface AuditCourse {
  code: string // "COMS 1013"
  title: string
  grade: string // as printed: A B C D F P W CE IP TA …
  credits: number
  term: string | null // "2025FA"
  exam: string | null // "AP07 - COMPUTER SCIENCE A" for credit by exam
  examProgram: 'AP' | 'CLEP' | 'IB' | null
  transfer: boolean
  section: 'requirement' | 'not_used' | 'in_progress'
}

/** One "Still needed" requirement: the courses that would satisfy it. */
export interface StillNeeded {
  label: string
  codes: string[]
  /** "9 Credits in @ 3@ or 4@": any 3000–4000 level course counts. */
  anyUpperLevel: boolean
}

export interface AuditImport {
  degree: string | null // "BS Computer Science"
  catalogYear: string | null // "2025-26"
  gpa: number | null
  creditsRequired: number | null
  creditsApplied: number | null
  courses: AuditCourse[]
  stillNeeded: StillNeeded[]
  unrecognized: string[]
}
