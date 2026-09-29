import type {
  DelayResponse,
  ExamOpportunitiesResponse,
  ExamsResponse,
  MetaResponse,
  PersonasResponse,
  PlanRequest,
  PlanResponse,
  ProgramDetail,
  ProgramListItem,
  WhatIfEvent,
  WhatIfResponse,
} from './types'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = 'Some inputs are invalid. Check the setup steps.'
    } catch {
      // keep the status text
    }
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  meta: () => request<MetaResponse>('/api/meta'),
  programs: () => request<ProgramListItem[]>('/api/programs'),
  program: (id: string) => request<ProgramDetail>(`/api/programs/${encodeURIComponent(id)}`),
  exams: () => request<ExamsResponse>('/api/exams'),
  personas: () => request<PersonasResponse>('/api/personas'),
  plan: (body: PlanRequest) => post<PlanResponse>('/api/plan', body),
  whatIf: (plan: PlanRequest, event: WhatIfEvent) => post<WhatIfResponse>('/api/plan/whatif', { plan, event }),
  examOpportunities: (body: PlanRequest) =>
    post<ExamOpportunitiesResponse>('/api/plan/exam-opportunities', body),
  delayImpact: (plan: PlanRequest, itemId: string) =>
    post<DelayResponse>('/api/plan/delay-impact', { plan, item_id: itemId }),
}
