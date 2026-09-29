import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the brand', () => {
    globalThis.fetch = vi.fn(() => Promise.reject(new Error('no network'))) as unknown as typeof fetch
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Shortcut' })).toBeInTheDocument()
  })
})
