import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { PlanRequest, PlanResponse } from '../api/types'

interface Result {
  key: string
  plan: PlanResponse | null
  error: string | null
}

/**
 * Fetch a plan whenever the request changes (debounced). The previous plan stays visible while
 * a new one is solving; `loading` is derived from whether the latest result matches the request.
 */
export function usePlan(request: PlanRequest | null): {
  plan: PlanResponse | null
  loading: boolean
  error: string | null
  retry: () => void
} {
  const [nonce, setNonce] = useState(0)
  const [result, setResult] = useState<Result | null>(null)
  const body = request ? JSON.stringify(request) : ''
  const key = body ? `${body}#${nonce}` : ''

  useEffect(() => {
    if (!body) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      api
        .plan(JSON.parse(body) as PlanRequest)
        .then((plan) => {
          if (!cancelled) setResult({ key, plan, error: null })
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            const message = err instanceof Error ? err.message : String(err)
            setResult((prev) => ({ key, plan: prev?.plan ?? null, error: message }))
          }
        })
    }, 150)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [body, key])

  return {
    plan: result?.plan ?? null,
    loading: Boolean(key) && result?.key !== key,
    error: result?.key === key ? result.error : null,
    retry: () => setNonce((n) => n + 1),
  }
}

/** Generic fetch-on-change hook with the same derived-loading pattern. */
export function useFetch<T>(key: string, load: (key: string) => Promise<T>): { data: T | null; loading: boolean; error: string | null } {
  const [result, setResult] = useState<{ key: string; data: T | null; error: string | null } | null>(null)
  useEffect(() => {
    if (!key) return
    let cancelled = false
    load(key)
      .then((data) => {
        if (!cancelled) setResult({ key, data, error: null })
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err)
          setResult((prev) => ({ key, data: prev?.data ?? null, error: message }))
        }
      })
    return () => {
      cancelled = true
    }
    // `load` is expected to be stable for a given key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return {
    data: result?.data ?? null,
    loading: Boolean(key) && result?.key !== key,
    error: result?.key === key ? result.error : null,
  }
}
