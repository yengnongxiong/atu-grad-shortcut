import type { Persona, ProgramListItem } from '../api/types'
import { ProgramPicker } from '../components/ProgramPicker'
import { Spinner } from '../components/ui'
import { navigate } from '../router'

export function Landing({
  programs,
  personas,
  loading,
  onPickProgram,
  onPersona,
}: {
  programs: ProgramListItem[]
  personas: Persona[]
  loading: boolean
  onPickProgram: (program: ProgramListItem) => void
  onPersona: (persona: Persona) => void
}) {
  const crossChecked = programs.filter((p) => p.trust_tier === 'cross_checked').length
  return (
    <div>
      <section className="border-b border-line bg-paper">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.15fr_1fr] lg:py-20">
          <div>
            <p className="eyebrow">For Arkansas Tech students · Unofficial</p>
            <h1 className="mt-3 text-4xl font-semibold leading-tight sm:text-5xl">
              The degree map is the path for the average student.{' '}
              <span className="text-muted">Shortcut is the path for you.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-ink-soft">
              Start from the credit you already have. Shortcut models summer, winter, heavier terms, overloads,
              CLEP, and transfer courses, then shows your fastest realistic graduation date, the courses that
              actually set it, and how much time each option buys.
            </p>
            <p className="mt-6">
              <a
                href="/import"
                className="btn-primary"
                onClick={(event) => {
                  event.preventDefault()
                  navigate('import')
                }}
              >
                Start from your Degree Works audit
              </a>
              <span className="mt-2 block text-sm text-muted">Read on your device. Or pick your major to enter credit by hand.</span>
            </p>
            <dl className="mt-8 grid max-w-lg grid-cols-3 gap-4 text-sm">
              <div>
                <dt className="text-muted">Majors</dt>
                <dd className="text-3xl font-semibold">{programs.length || '—'}</dd>
              </div>
              <div>
                <dt className="text-muted">Cross-checked</dt>
                <dd className="text-3xl font-semibold">{programs.length ? crossChecked : '—'}</dd>
              </div>
              <div>
                <dt className="text-muted">Per plan</dt>
                <dd className="text-3xl font-semibold">~2 s</dd>
              </div>
            </dl>
          </div>
          <div className="card p-5 sm:p-6">
            <h2 className="text-2xl font-semibold">Find your major</h2>
            <p className="mt-1 text-sm text-muted">Every bachelor’s degree map ATU publishes, labeled by how much we trust the data.</p>
            <div className="mt-4">
              {loading ? <Spinner label="Loading majors…" /> : <ProgramPicker programs={programs} onSelect={onPickProgram} compact />}
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="eyebrow">One-click demos</p>
            <h2 className="text-3xl font-semibold">See it with a real scenario</h2>
          </div>
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {personas.map((persona, index) => (
            <button
              key={persona.id}
              type="button"
              onClick={() => onPersona(persona)}
              className="card flex flex-col items-start p-5 text-left hover:border-ink"
            >
              <span className="eyebrow">P{index + 1}</span>
              <span className="mt-1 text-lg font-semibold">{persona.name}</span>
              <span className="mt-2 text-sm text-ink-soft">{persona.tagline}</span>
              {persona.sample_data && (
                <span className="chip mt-3">Sample data</span>
              )}
              <span className="mt-auto pt-4 text-sm font-medium underline underline-offset-2">Open plan</span>
            </button>
          ))}
          {!loading && personas.length === 0 && <p className="text-sm text-muted">No demo profiles available.</p>}
        </div>
      </section>

      <section className="border-t border-line">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-3">
          <div>
            <p className="eyebrow">01 · Your starting point</p>
            <h3 className="mt-2 text-xl font-semibold">Credit you already have</h3>
            <p className="mt-2 text-sm text-ink-soft">Completed courses with grades, CLEP scores, transfer credit, and your math ACT for placement.</p>
          </div>
          <div>
            <p className="eyebrow">02 · Every lever ATU allows</p>
            <h3 className="mt-2 text-xl font-semibold">Priced in terms saved</h3>
            <p className="mt-2 text-sm text-ink-soft">Each option shows its marginal effect, what it costs, and whose approval it needs.</p>
          </div>
          <div>
            <p className="eyebrow">03 · What actually sets the date</p>
            <h3 className="mt-2 text-xl font-semibold">The critical chain</h3>
            <p className="mt-2 text-sm text-ink-soft">Miss one link in a fall-only chain and graduation slips a year. Shortcut shows which link.</p>
          </div>
        </div>
      </section>
    </div>
  )
}
