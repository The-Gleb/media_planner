export interface ProblemDetails {
  type: string
  title: string
  status: number
  detail?: string
  instance?: string
  code: string
  trace_id?: string
  errors?: Array<{ field: string; code: string; detail?: string }>
}

export interface SimulationConfigPayload {
  audience?: import('../domain/audience').Audience
  world_seed: string
  campaign_seed: string
  start_hour: string
  duration_hours: number
  time_zone: string
  disable_random_events?: boolean
  scenario_events?: Array<{ channel_id: string; metric: 'supply' | 'cpm' | 'ctr' | 'cr' | 'pause'; start_index: number; duration_hours: number; multiplier: number }>
}

export interface StepPayload {
  audience?: import('../domain/audience').Audience
  step_id: string
  actions: Array<{ channel_id: string; budget_cap: string }>
}
