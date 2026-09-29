import { useId, useMemo, useState } from 'react'
import type { ProgramListItem } from '../api/types'
import { TrustBadge } from './ui'

function matches(program: ProgramListItem, query: string): boolean {
  const haystack = `${program.listed_title} ${program.name} ${program.college} ${program.degree_abbr} ${program.catalog_year}`.toLowerCase()
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word))
}

export function ProgramPicker({
  programs,
  value,
  onSelect,
  autoFocus = false,
  compact = false,
}: {
  programs: ProgramListItem[]
  value?: string
  onSelect: (program: ProgramListItem) => void
  autoFocus?: boolean
  compact?: boolean
}) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const listId = useId()
  const results = useMemo(() => programs.filter((p) => matches(p, query)).slice(0, compact ? 6 : 10), [programs, query, compact])
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
                {[program.degree_abbr || program.degree, program.college, `${program.catalog_year} catalog`].filter(Boolean).join(' · ')}
              </span>
            </span>
            <TrustBadge tier={program.trust_tier} compact />
          </li>
        ))}
      </ul>
      {selected?.trust_tier === 'needs_review' && (
        <p role="note" className="mt-2 rounded-md border border-warn/40 bg-warn-soft px-3 py-2 text-sm text-warn">
          <strong>Needs review:</strong> automated checks found problems in this program’s data ({selected.issues.length}{' '}
          issue{selected.issues.length === 1 ? '' : 's'}). You can still plan, but compare the result with the degree map.
        </p>
      )}
    </div>
  )
}
