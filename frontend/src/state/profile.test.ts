import { decodeRequest, defaultLevers, defaultProfile, encodeRequest, normalizeRequest, termLabel } from './profile'

describe('profile state', () => {
  it('round-trips a request through the share URL encoding', () => {
    const request = {
      profile: { ...defaultProfile('computer-science-2025-26'), math_act: 27, exams: [{ program: 'CLEP' as const, exam: 'Calculus', score: 58 }] },
      levers: { ...defaultLevers(), summer: true, planned_exams: ['clep-calculus-50'] },
    }
    const decoded = decodeRequest(encodeRequest(request))
    expect(decoded).toEqual(request)
  })

  it('keeps posted exam credit and record hours through the share URL', () => {
    const request = {
      profile: {
        ...defaultProfile('computer-science-2025-26'),
        completed: [{ code: 'COMS 1411', grade: 'P' as const, source: 'exam' as const, hours: 1, exam: 'AP35 - COMPUTER SCIENCE PRINCIPLES' }],
      },
      levers: defaultLevers(),
    }
    expect(decodeRequest(encodeRequest(request))?.profile.completed).toEqual(request.profile.completed)
  })

  it('rejects garbage and fills missing fields with defaults', () => {
    expect(decodeRequest('not-base64!!')).toBeNull()
    expect(normalizeRequest({ p: { first_term: '2026FA' } })).toBeNull()
    const partial = normalizeRequest({ p: { program_id: 'x' }, l: { summer: 'yes' } })
    expect(partial?.levers.summer).toBe(false)
    expect(partial?.profile.preferences.mode).toBe('conservative')
  })

  it('labels terms like the backend', () => {
    expect(termLabel('2026FA')).toBe('Fall 2026')
    expect(termLabel('2026WI')).toBe('Winter 2026–27')
    expect(termLabel('2027SU')).toBe('Summer 2027')
  })
})
