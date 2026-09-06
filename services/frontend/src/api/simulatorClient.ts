import { decodeAudienceCatalog } from './audienceCodecs'
import { decodeActiveRun, decodeProblem, decodeStepResult, decodeWorldMetadata } from './codecs'
import type { ProblemDetails, SimulationConfigPayload, StepPayload } from './types'

export class SimulatorProblemError extends Error {
  constructor(public readonly problem: ProblemDetails) {
    super(problem.detail ?? problem.title)
    this.name = 'SimulatorProblemError'
  }
}

export interface ResponseWithETag<T> { data: T; etag: string | null }
export interface AudienceSegment { segmentId: string; geo: string; gender: string; ageFrom: number; ageToExclusive: number }
export interface AudienceSegments { engineVersion: string; worldConfigDigest: string; channels: { channelId: string; segments: AudienceSegment[] }[] }

export class SimulatorClient {
  constructor(private readonly fetcher: typeof fetch = globalThis.fetch.bind(globalThis)) {}

  async ready(): Promise<boolean> {
    const response = await this.fetcher('/api/health/ready', { headers: { Accept: 'application/json' } })
    return response.ok
  }

  async audienceCatalog() {
    try { const response = await this.request('/api/v1/audience-segments'); return decodeAudienceCatalog(await response.json()) }
    catch (error) { if (error instanceof SimulatorProblemError && error.problem.status === 404) return null; throw error }
  }

  async metadata() {
    const response = await this.request('/api/v1/world-metadata')
    return decodeWorldMetadata(await response.json())
  }

  /** Public synthetic segment catalogue; hidden capacities and multipliers are never exposed. */
  async audienceSegments(): Promise<AudienceSegments> {
    const response = await this.request('/api/v1/audience-segments')
    const raw = await response.json() as Record<string, unknown>
    if (typeof raw.engine_version !== 'string' || typeof raw.world_config_digest !== 'string' || !Array.isArray(raw.channels)) throw new Error('invalid_audience_segments')
    return {
      engineVersion: raw.engine_version, worldConfigDigest: raw.world_config_digest,
      channels: raw.channels.map((channel) => {
        const item = channel as Record<string, unknown>
        const segments = Array.isArray(item.segments) ? item.segments as Record<string, unknown>[] : []
        return { channelId: String(item.channel_id), segments: segments.map((segment) => ({ segmentId: String(segment.segment_id), geo: String(segment.geo), gender: String(segment.gender), ageFrom: Number(segment.age_from), ageToExclusive: Number(segment.age_to_exclusive) })) }
      }),
    }
  }

  async putSimulation(id: string, payload: SimulationConfigPayload, etag: string | null): Promise<ResponseWithETag<ReturnType<typeof decodeActiveRun>>> {
    const headers: Record<string, string> = { Accept: 'application/json', 'Content-Type': 'application/json' }
    if (etag) headers['If-Match'] = etag
    else headers['If-None-Match'] = '*'
    const response = await this.request(`/api/v1/simulations/${encodeURIComponent(id)}`, {
      method: 'PUT', headers, body: JSON.stringify(payload),
    })
    const nextETag = response.headers.get('ETag')
    return { data: decodeActiveRun(await response.json(), nextETag), etag: nextETag }
  }

  async currentHour(id: string): Promise<ResponseWithETag<{ simulationId: string; status: 'active' | 'finished'; currentHour: string; remainingHours: number }>> {
    const response = await this.request(`/api/v1/simulations/${encodeURIComponent(id)}/current-hour`)
    const raw = await response.json() as Record<string, unknown>
    if (typeof raw.simulation_id !== 'string' || (raw.status !== 'active' && raw.status !== 'finished') || typeof raw.current_hour !== 'string' || !Number.isSafeInteger(raw.remaining_hours)) {
      throw new Error('invalid_current_hour')
    }
    return { data: { simulationId: raw.simulation_id, status: raw.status, currentHour: raw.current_hour, remainingHours: raw.remaining_hours as number }, etag: response.headers.get('ETag') }
  }

  async step(id: string, payload: StepPayload, etag: string | null) {
    const headers: Record<string, string> = { Accept: 'application/json', 'Content-Type': 'application/json' }
    if (etag) headers['If-Match'] = etag
    const response = await this.request(`/api/v1/simulations/${encodeURIComponent(id)}/steps`, {
      method: 'POST', headers, body: JSON.stringify(payload),
    })
    return { data: decodeStepResult(await response.json()), etag: response.headers.get('ETag') }
  }

  private async request(input: string, init: RequestInit = {}): Promise<Response> {
    let response: Response
    try {
      response = await this.fetcher(input, { ...init, headers: { Accept: 'application/json', ...init.headers } })
    } catch (cause) {
      throw new Error('simulator_unreachable', { cause })
    }
    if (!response.ok) {
      let body: unknown = {}
      try { body = await response.json() } catch { /* non-JSON upstream failure */ }
      throw new SimulatorProblemError(decodeProblem(body, response.status))
    }
    return response
  }
}

export const simulatorClient = new SimulatorClient()
