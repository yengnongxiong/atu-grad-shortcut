// PRD v1.1 §3.5: white background, gray borders, no tinted panels. Hover, selected, and
// disabled states may shade a control; the red error box is the one tinted panel allowed.
const sources = import.meta.glob(['./**/*.{ts,tsx}', '!./**/*.test.{ts,tsx}', '!./test/**'], {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

function offending(pattern: RegExp): string[] {
  return Object.entries(sources).flatMap(([file, text]) =>
    text
      .split('\n')
      .map((line, i) => ({ line: line.trim(), at: `${file}:${String(i + 1)}` }))
      .filter(({ line }) => pattern.test(line))
      .map(({ at, line }) => `${at}  ${line}`),
  )
}

describe('minimal visual design', () => {
  it('scans the component sources', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(20)
  })

  it('has no tinted panels or tags', () => {
    expect(offending(/bg-(critical|saved|warn|info)-soft/)).toEqual([])
  })

  it('has no shaded table headers', () => {
    expect(offending(/<thead[^>]*\bbg-(?!surface\b)/)).toEqual([])
  })

  it('draws with black, white, and grays only', () => {
    const colored = offending(/#[0-9a-fA-F]{6}\b/).filter((hit) =>
      [...hit.matchAll(/#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})\b/g)].some(([, r, g, b]) => r !== g || g !== b),
    )
    expect(colored).toEqual([])
  })

  it('keeps notes as bordered text', () => {
    expect(offending(/role="note"[^>]*\bbg-/)).toEqual([])
  })
})
