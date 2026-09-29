import { useEffect, useState } from 'react'

export type Route = 'landing' | 'import' | 'setup' | 'plan' | 'about'

const PATHS: Record<Route, string> = {
  landing: '/',
  import: '/import',
  setup: '/setup',
  plan: '/plan',
  about: '/about',
}

export function routeFromPath(pathname: string): Route {
  const clean = pathname.replace(/\/+$/, '') || '/'
  const match = (Object.entries(PATHS) as [Route, string][]).find(([, path]) => path === clean)
  return match ? match[0] : 'landing'
}

export function navigate(route: Route, search = ''): void {
  const url = `${PATHS[route]}${search}`
  if (`${window.location.pathname}${window.location.search}` !== url) {
    window.history.pushState({}, '', url)
  }
  window.dispatchEvent(new PopStateEvent('popstate'))
  window.scrollTo({ top: 0 })
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => routeFromPath(window.location.pathname))
  useEffect(() => {
    const onPop = () => setRoute(routeFromPath(window.location.pathname))
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  return route
}
