import type { AuditCourse, AuditImport, StillNeeded } from './types'

/**
 * Read a Degree Works audit from its text lines (one string per visual line, as pdf.js gives
 * them). The parser keys off stable tokens (course codes, the grade column, "Satisfied by:",
 * "Still needed:") rather than page positions, and it never keeps the student's name or ID.
 */

const GRADES = 'A|B|C|D|F|P|W|CE|IP|CR|NC|TA|TB|TC|TD|TP|TR'
const ROW = new RegExp(
  String.raw`\b([A-Z]{2,4}) (\d{4})\s+(.+?)\s+(${GRADES})\s+\(?(\d+(?:\.\d+)?)\)?\s+(Fall|Spring|Summer|Winter)(?: Term)?(?:\s+(\d{4}))?\s*$`,
)
const SEASON: Record<string, string> = { Fall: 'FA', Spring: 'SP', Summer: 'SU', Winter: 'WI' }
const PAGE_HEADER = /^Arkansas Tech University\b.*-\s*T\d{8}\s*$/
const WRAPPED_YEAR = /^(.*?)\s*\b(\d{4})$/
const CODE_TOKENS = /\b([A-Z]{2,4})\s+(\d{4})\b|\b(\d{4})\b/g
const CONTINUATION = /^(?:or\s+)?(?:[A-Z]{2,4}\s+)?\d{4}\b(?:\s+or\b.*|\s*)$|^(?:[A-Z]{2,4}\s+)?\d{4}(?:\s+or\s+(?:[A-Z]{2,4}\s+)?\d{4})*(?:\s+or)?$/

/** Course codes in "PHSC 1013 or 1053 or CHEM 1113", carrying the subject to bare numbers. */
function codesIn(text: string, subject: string | null = null): { codes: string[]; subject: string | null } {
  const codes: string[] = []
  let current = subject
  for (const m of text.matchAll(CODE_TOKENS)) {
    if (m[1]) current = m[1]
    const number = m[2] ?? m[3]
    if (current && number) codes.push(`${current} ${number}`)
  }
  return { codes, subject: current }
}

function sectionOf(line: string, current: AuditCourse['section']): AuditCourse['section'] {
  if (/^Not Used\b/.test(line)) return 'not_used'
  if (/^In-progress\s+Credits applied/.test(line)) return 'in_progress'
  if (/^(Legend|Disclaimer)\b/.test(line)) return 'requirement'
  return current
}

export function parseAudit(lines: string[]): AuditImport {
  const text = lines.join('\n')
  const catalog = text.match(/Catalog year:\s*(\d{4})-\d{2}(\d{2})/)
  const credits = text.match(/Credits required:\s*(\d+)\s+Credits applied:\s*(\d+)/)
  const gpa = text.match(/Overall GPA[\s\S]{0,120}?\b(\d\.\d{3})\b/)
  const degree = text.match(/^Degree\s+(?!progress\b)(.+)$/m)

  const courses = new Map<string, AuditCourse>()
  const stillNeeded: StillNeeded[] = []
  const unrecognized: string[] = []
  let section: AuditCourse['section'] = 'requirement'
  let last: AuditCourse | null = null
  let lastLabel = '' // the requirement label printed before the last course row ("Social Sciences")
  let open: { need: StillNeeded; subject: string | null; block: boolean } | null = null

  for (let i = 0; i < lines.length; i++) {
    const line = (lines[i] ?? '').trim()
    if (!line || PAGE_HEADER.test(line)) continue
    section = sectionOf(line, section)

    const satisfied = line.match(/^Satisfied by:\s*(.+)$/)
    if (satisfied) {
      if (last) {
        const exam = (satisfied[1] ?? '').match(/^(.*?)\s*-\s*Credit by (AP|CLEP|IB) Exam\b/)
        if (exam) {
          last.exam = (exam[1] ?? '').trim()
          last.examProgram = exam[2] as 'AP' | 'CLEP' | 'IB'
        } else if (last.grade.startsWith('T')) {
          last.transfer = true
        }
      }
      continue
    }

    const needed = line.match(/^(.*?)\s*Still needed:\s*(.*)$/)
    if (needed) {
      const printed = (needed[1] ?? '').trim()
      const rest = needed[2] ?? ''
      const label = printed || lastLabel
      open = null
      if (/Choose from \d+ of the following/.test(rest)) {
        open = { need: { label, codes: [], anyUpperLevel: false }, subject: null, block: true }
        stillNeeded.push(open.need)
      } else if (/Credits? in @ 3@ or 4@/.test(rest)) {
        stillNeeded.push({ label, codes: [], anyUpperLevel: true })
      } else if (/\bClass(?:es)? in\b|\bCredits? in\b/.test(rest)) {
        const found = codesIn(rest.replace(/^.*?\bin\b/, ''))
        open = { need: { label, codes: found.codes, anyUpperLevel: false }, subject: found.subject, block: false }
        stillNeeded.push(open.need)
      }
      continue
    }
    if (open) {
      const blockLine = open.block && /\bClass(?:es)? in\b/.test(line)
      if (blockLine || CONTINUATION.test(line)) {
        const found = codesIn(blockLine ? line.replace(/^.*?\bin\b/, '') : line, blockLine ? null : open.subject)
        open.need.codes.push(...found.codes.filter((c) => !open?.need.codes.includes(c)))
        open.subject = found.subject
        continue
      }
      if (open.block && /You must complete all of the following/.test(line)) continue
      open = null
    }

    const row = line.match(ROW)
    if (row) {
      const [, subject = '', number = '', title = '', grade = '', hours = '0', season = 'Fall', year] = row
      const printedLabel = line.slice(0, row.index).trim()
      if (printedLabel) lastLabel = printedLabel
      let fullTitle = title.trim()
      let termYear = year
      if (!termYear) {
        const wrapped = (lines[i + 1] ?? '').trim().match(WRAPPED_YEAR)
        if (wrapped) {
          termYear = wrapped[2]
          if (wrapped[1]) fullTitle = `${fullTitle} ${wrapped[1]}`
          i++
        }
      }
      const code = `${subject} ${number}`
      const course: AuditCourse = {
        code,
        title: fullTitle,
        grade,
        credits: Number(hours),
        term: termYear ? `${termYear}${SEASON[season]}` : null,
        exam: null,
        examProgram: null,
        transfer: false,
        section,
      }
      if (!courses.has(code)) courses.set(code, course)
      last = courses.get(code) ?? null
      continue
    }
    if (/\b[A-Z]{2,4} \d{4}\b/.test(line) && /\b(Fall|Spring|Summer|Winter) Term\b/.test(line)) unrecognized.push(line)
  }

  return {
    degree: degree?.[1]?.trim() ?? null,
    catalogYear: catalog ? `${catalog[1]}-${catalog[2]}` : null,
    gpa: gpa ? Number(gpa[1]) : null,
    creditsRequired: credits ? Number(credits[1]) : null,
    creditsApplied: credits ? Number(credits[2]) : null,
    courses: [...courses.values()],
    stillNeeded,
    unrecognized,
  }
}
