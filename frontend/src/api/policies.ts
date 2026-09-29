import { useEffect, useState } from 'react'
import { api } from './client'
import type { PolicyOut } from './types'

export type Policies = Record<string, PolicyOut>

let pending: Promise<Policies> | null = null

/** Every policy the planner uses, from /api/meta, fetched once per page load (numbers live only in policies.json). */
export function loadPolicies(): Promise<Policies> {
  pending ??= api.meta().then(
    (meta) => Object.fromEntries(meta.policies.map((p) => [p.key, p])),
    (err: unknown) => {
      pending = null
      throw err
    },
  )
  return pending
}

export function usePolicies(): Policies | null {
  const [policies, setPolicies] = useState<Policies | null>(null)
  useEffect(() => {
    let live = true
    loadPolicies()
      .then((p) => {
        if (live) setPolicies(p)
      })
      .catch(() => undefined)
    return () => {
      live = false
    }
  }, [])
  return policies
}

export function policyNumber(policies: Policies | null, key: string): number | null {
  const value = policies?.[key]?.value
  return typeof value === 'number' ? value : null
}
