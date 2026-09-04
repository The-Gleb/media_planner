import type { ProblemDetails } from './types'

export class PlannerProblemError extends Error {
  constructor(public readonly problem: ProblemDetails) { super(problem.detail ?? problem.title); this.name = 'PlannerProblemError' }
}
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
export function decodePlannerProblem(raw: unknown, fallbackStatus: number): ProblemDetails {
  if (!object(raw)) return { type: 'about:blank', title: 'Planner error', status: fallbackStatus, code: 'planner_error' }
  const errors = Array.isArray(raw.errors) ? raw.errors.flatMap((item) => object(item) && typeof item.field === 'string' && typeof item.code === 'string'
    ? [{ field: item.field, code: item.code, ...(typeof item.detail === 'string' ? { detail: item.detail } : {}) }] : []) : undefined
  return { type: typeof raw.type === 'string' ? raw.type : 'about:blank', title: typeof raw.title === 'string' ? raw.title : 'Planner error',
    status: typeof raw.status === 'number' && Number.isInteger(raw.status) ? raw.status : fallbackStatus,
    ...(typeof raw.detail === 'string' ? { detail: raw.detail } : {}), ...(typeof raw.instance === 'string' ? { instance: raw.instance } : {}),
    code: typeof raw.code === 'string' ? raw.code : 'planner_error', ...(typeof raw.trace_id === 'string' ? { trace_id: raw.trace_id } : {}), ...(errors ? { errors } : {}) }
}
