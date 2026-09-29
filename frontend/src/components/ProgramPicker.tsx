import { useId, useMemo, useState } from 'react'
import type { ProgramListItem } from '../api/types'
import { onePerMajor, versionsOf } from '../catalogYear'
import { TrustBadge } from './ui'

function matches(program: ProgramListItem, query: string): boolean {
  const haystack = `${program.listed_title} ${program.name} ${program.college} ${program.degree_abbr} ${program.catalog_year}`.toLowerCase()
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word))
}

function yearsLabel(programs: ProgramListItem[], program: ProgramListItem): string {
  const others = versionsOf(programs, program.id).filter((p) => p.id !== program.id)
  return `${program.catalog_year} catalog${others.length ? ` · also ${others.map((p) => p.catalog_year).join(', ')}` : ''}`
}

export function ProgramPicker({
  programs,
  value,
  onSelect,
  autoFocus = false,
  compact = false,
  preferredYear,
}: {
  programs: ProgramListItem[]
  value?: string
  onSelect: (program: ProgramListItem) => void
  autoFocus?: boolean
  compact?: boolean
  /** Catalog year to pick when a major has several (the student's catalog of entry). */
  preferredYear?: string
}) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const listId = useId()
  const results = useMemo(
    () => onePerMajor(programs.filter((p) => matches(p, query)), preferredYear).slice(0, compact ? 6 : 10),
    [programs, query, compact, preferredYear],
  )
  const selected = programs.find((p) => p.id === value)
  const showList = !selected || query.trim() !== ''

  const choose = (program: ProgramListItem | undefined) => {
    if (!program) return
    onSelect(program)
    setQuery('')
  }

  return (
    <div className="w-full">
      <label htmlFor={`${listId}-input`} className="sr-only">
        Search majors
      </label>
      <input
        id={`${listId}-input`}
        className="input h-12 text-base"
        placeholder={selected ? `${selected.listed_title} — search to change` : 'Search 70+ ATU majors, e.g. “computer science”'}
        value={query}
        autoFocus={autoFocus}
        role="combobox"
        aria-expanded={showList && results.length > 0}
        aria-controls={listId}
        aria-activedescendant={results[active] ? `${listId}-${results[active].id}` : undefined}
        onChange={(event) => {
          setQuery(event.target.value)
          setActive(0)
        }}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown') {
            event.preventDefault()
            setActive((a) => Math.min(a + 1, results.length - 1))
          } else if (event.key === 'ArrowUp') {
            event.preventDefault()
            setActive((a) => Math.max(a - 1, 0))
          } else if (event.key === 'Enter') {
            event.preventDefault()
            choose(results[active])
          }
        }}
      />
      <ul
        id={listId}
        role="listbox"
        aria-label="Majors"
        hidden={!showList}
        className="mt-2 divide-y divide-line overflow-hidden rounded-md border border-line bg-surface"
      >
        {results.length === 0 && <li className="px-4 py-3 text-sm text-muted">No majors match “{query}”.</li>}
        {results.map((program, index) => (
          <li
            key={program.id}
            id={`${listId}-${program.id}`}
            role="option"
            aria-selected={program.id === value}
            className={`flex cursor-pointer flex-wrap items-center justify-between gap-2 px-4 py-2.5 ${
              index === active ? 'bg-paper-deep' : ''
            } ${program.id === value ? 'border-l-4 border-l-ink' : ''}`}
            onMouseEnter={() => setActive(index)}
            onClick={() => choose(program)}
          >
            <span className="min-w-0">
              <span className="block truncate font-medium">{program.listed_title}</span>
              <span className="block truncate text-xs text-muted">
                {[program.degree_abbr || program.degree, program.college, yearsLabel(programs, program)].filter(Boolean).join(' · ')}
              </span>
            </span>
            <TrustBadge tier={program.trust_tier} compact />
          </li>
        ))}
      </ul>
      {selected?.trust_tier === 'needs_review' && (
        <p role="note" className="mt-2 rounded-md border border-ink px-3 py-2 text-sm">
          <strong>Needs review:</strong> automated checks found problems in this program’s data ({selected.issues.length}{' '}
          issue{selected.issues.length === 1 ? '' : 's'}). You can still plan, but compare the result with the degree map.
        </p>
      )}
    </div>
  )
}
