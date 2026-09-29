import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client'
import type { Persona, PlanRequest, ProgramListItem } from './api/types'
import { Layout } from './components/Layout'
import { ErrorBox } from './components/ui'
import { About } from './pages/About'
import { Landing } from './pages/Landing'
import { PlanPage } from './pages/PlanPage'
import { Setup } from './pages/Setup'
import { navigate, useRoute } from './router'
import { SHARE_PARAM, decodeRequest, defaultRequest, encodeRequest, loadRequest, saveRequest } from './state/profile'

function initialRequest(): PlanRequest | null {
  const shared = new URLSearchParams(window.location.search).get(SHARE_PARAM)
  if (shared) {
    const decoded = decodeRequest(shared)
    if (decoded) return decoded
  }
  return loadRequest()
}

export default function App() {
  const route = useRoute()
  const [request, setRequest] = useState<PlanRequest | null>(initialRequest)
  const [programs, setPrograms] = useState<ProgramListItem[]>([])
  const [personas, setPersonas] = useState<Persona[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.programs(), api.personas()])
      .then(([programList, personaList]) => {
        setPrograms(programList)
        setPersonas(personaList.personas)
        setLoadError(null)
      })
      .catch((err: unknown) => setLoadError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false))
  }, [])

  const update = useCallback((next: PlanRequest) => {
    setRequest(next)
    saveRequest(next)
    if (window.location.pathname === '/plan') {
      window.history.replaceState({}, '', `/plan?${SHARE_PARAM}=${encodeRequest(next)}`)
    }
  }, [])

  const openPlan = (next: PlanRequest) => {
    update(next)
    navigate('plan', `?${SHARE_PARAM}=${encodeRequest(next)}`)
  }

  return (
    <Layout route={route} hasPlan={Boolean(request?.profile.program_id)}>
      {loadError && (
        <div className="mx-auto max-w-3xl px-4 pt-6">
          <ErrorBox message={`Couldn’t reach the Shortcut API: ${loadError}`} onRetry={() => window.location.reload()} />
        </div>
      )}
      {route === 'landing' && (
        <Landing
          programs={programs}
          personas={personas}
          loading={loading}
          onPickProgram={(program) => {
            update(defaultRequest(program.id))
            navigate('setup')
          }}
          onPersona={(persona) => openPlan(persona.request)}
        />
      )}
      {route === 'setup' && <Setup request={request} programs={programs} onChange={update} onBuild={openPlan} />}
      {route === 'plan' && <PlanPage request={request} programs={programs} onChange={update} />}
      {route === 'about' && <About programs={programs} />}
    </Layout>
  )
}
