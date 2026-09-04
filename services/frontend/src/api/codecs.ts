import type { ProblemDetails } from './types'
import type { ActiveRun, HourlyResult, Observation, WorldMetadata } from '../domain/types'
import { decodeSafeCount, parseMoney } from '../domain/numeric'

type UnknownRecord = Record<string, unknown>

function record(value: unknown, name: string): UnknownRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`invalid_${name}`)
  return value as UnknownRecord
}
function text(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.length === 0) throw new Error(`invalid_${field}`)
  return value
}
function integer(value: unknown, field: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new Error(`invalid_${field}`)
  return value
}
function status(value: unknown): 'active' | 'finished' {
  if (value !== 'active' && value !== 'finished') throw new Error('invalid_status')
  return value
}
function money(value: unknown, field: string): string {
  const result = text(value, field)
  parseMoney(result)
  return result
}
function channelIds(value: unknown): string[] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 20) throw new Error('invalid_channel_ids')
  const result = value.map((item) => text(item, 'channel_id'))
  if (new Set(result).size !== result.length) throw new Error('duplicate_channel_id')
  return result
}

export function decodeWorldMetadata(value: unknown): WorldMetadata {
  const v = record(value, 'world_metadata')
  const digest = text(v.world_config_digest, 'world_config_digest')
  const currency = text(v.currency, 'currency')
  if (!/^[a-f0-9]{64}$/.test(digest) || !/^[A-Z]{3}$/.test(currency)) throw new Error('invalid_world_metadata')
  return {
    engineVersion: text(v.engine_version, 'engine_version'),
    worldConfigDigest: digest,
    currency,
    channelIds: channelIds(v.channel_ids),
  }
}

export function decodeActiveRun(value: unknown, etag: string | null): ActiveRun {
  const v = record(value, 'campaign_session')
  return {
    simulationId: text(v.simulation_id, 'simulation_id'),
    status: status(v.status),
    currentHour: text(v.current_hour, 'current_hour'),
    endHourExclusive: text(v.end_hour_exclusive, 'end_hour_exclusive'),
    durationHours: integer(v.duration_hours, 'duration_hours'),
    remainingHours: integer(v.remaining_hours, 'remaining_hours'),
    timeZone: text(v.time_zone, 'time_zone'),
    currency: text(v.currency, 'currency'),
    engineVersion: text(v.engine_version, 'engine_version'),
    worldConfigDigest: text(v.world_config_digest, 'world_config_digest'),
    channelIds: channelIds(v.channel_ids),
    etag,
  }
}

function decodeObservation(value: unknown): Observation {
  const v = record(value, 'observation')
  const impressions = decodeSafeCount(v.impressions, 'impressions')
  const requests = decodeSafeCount(v.requests, 'requests')
  const uniqueReach = decodeSafeCount(v.unique_reach, 'unique_reach')
  const clicks = decodeSafeCount(v.clicks, 'clicks')
  const conversions = decodeSafeCount(v.conversions, 'conversions')
  if (impressions > requests || uniqueReach > impressions || clicks > impressions || conversions > clicks) {
    throw new Error('invalid_funnel')
  }
  const ecpm = v.ecpm === null ? null : money(v.ecpm, 'ecpm')
  if ((impressions === 0n) !== (ecpm === null)) throw new Error('invalid_ecpm_nullability')
  return {
    channelId: text(v.channel_id, 'channel_id'),
    hour: text(v.hour, 'hour'),
    requests,
    impressions,
    uniqueReach,
    clicks,
    conversions,
    spend: money(v.spend, 'spend'),
    ecpm,
  }
}

export function decodeStepResult(value: unknown): HourlyResult {
  const v = record(value, 'step_result')
  if (!Array.isArray(v.observations) || v.observations.length === 0) throw new Error('invalid_observations')
  return {
    simulationId: text(v.simulation_id, 'simulation_id'),
    stepId: text(v.step_id, 'step_id'),
    observedHour: text(v.observed_hour, 'observed_hour'),
    nextHour: text(v.next_hour, 'next_hour'),
    status: status(v.status),
    remainingHours: integer(v.remaining_hours, 'remaining_hours'),
    observations: v.observations.map(decodeObservation),
  }
}

export function decodeProblem(value: unknown, fallbackStatus: number): ProblemDetails {
  const v = record(value, 'problem')
  return {
    type: typeof v.type === 'string' ? v.type : 'about:blank',
    title: typeof v.title === 'string' ? v.title : 'Request failed',
    status: typeof v.status === 'number' ? v.status : fallbackStatus,
    detail: typeof v.detail === 'string' ? v.detail : undefined,
    instance: typeof v.instance === 'string' ? v.instance : undefined,
    code: typeof v.code === 'string' ? v.code : 'unknown_error',
    trace_id: typeof v.trace_id === 'string' ? v.trace_id : undefined,
    errors: Array.isArray(v.errors) ? v.errors.flatMap((item) => {
      const e = record(item, 'field_error')
      return typeof e.field === 'string' && typeof e.code === 'string'
        ? [{ field: e.field, code: e.code, detail: typeof e.detail === 'string' ? e.detail : undefined }]
        : []
    }) : undefined,
  }
}
