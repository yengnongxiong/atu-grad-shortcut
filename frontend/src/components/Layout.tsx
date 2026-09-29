import type { ReactNode } from 'react'
import { navigate, type Route } from '../router'

export const DISCLAIMER =
  'Not affiliated with Arkansas Tech University. Not official advising. Confirm your plan with your advisor.'

export function Wordmark() {
  return (
    <span className="inline-flex items-center gap-2">
      <svg viewBox="0 0 32 32" aria-hidden="true" className="h-7 w-7">
        <rect width="32" height="32" rx="7" fill="#16181d" />
        <path d="M7 22 C 12 22, 13 10, 25 10" fill="none" stroke="#f5b83d" strokeWidth="3" strokeLinecap="round" />
        <path d="M20.5 6.5 25 10 21 14" fill="none" stroke="#f5b83d" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="font-display text-xl font-semibold tracking-tight">Shortcut</span>
    </span>
  )
}

function NavLink({ to, current, children }: { to: Route; current: Route; children: ReactNode }) {
  const active = to === current
  return (
    <a
      href={to === 'landing' ? '/' : `/${to}`}
      aria-current={active ? 'page' : undefined}
      onClick={(event) => {
        event.preventDefault()
        navigate(to)
      }}
      className={`rounded-md px-3 py-1.5 text-sm font-medium no-underline ${
        active ? 'bg-ink text-paper' : 'text-ink-soft hover:bg-paper-deep'
      }`}
    >
      {children}
    </a>
  )
}

export function Layout({ route, children, hasPlan }: { route: Route; children: ReactNode; hasPlan: boolean }) {
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
        Skip to content
      </a>
      <header className="no-print border-b border-line bg-paper/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <a
            href="/"
            className="no-underline"
            onClick={(event) => {
              event.preventDefault()
              navigate('landing')
            }}
            aria-label="Shortcut home"
          >
            <Wordmark />
          </a>
          <nav aria-label="Main" className="flex items-center gap-1">
            <NavLink to="setup" current={route}>
              Setup
            </NavLink>
            {hasPlan && (
              <NavLink to="plan" current={route}>
                My plan
              </NavLink>
            )}
            <NavLink to="about" current={route}>
              About the data
            </NavLink>
          </nav>
        </div>
      </header>
      <main id="main" className="flex-1">
        {children}
      </main>
      <footer className="border-t border-line bg-paper-deep">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p className="font-medium text-ink-soft">{DISCLAIMER}</p>
          <p>A portfolio project. Data: public ATU degree maps, course catalog, and class schedules.</p>
        </div>
      </footer>
    </div>
  )
}
