import { useEffect, useState } from 'react'

export default function App() {
  const [status, setStatus] = useState<string>('checking…')

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json() as Promise<{ status: string }>)
      .then((d) => setStatus(d.status))
      .catch(() => setStatus('offline'))
  }, [])

  return (
    <main className="p-8">
      <h1 className="text-3xl font-semibold">Shortcut</h1>
      <p>API: {status}</p>
    </main>
  )
}
