export interface ChannelAudience { segment_ids: string[] }
export type Audience = Record<string, ChannelAudience>
export interface AudienceSegment { segment_id: string; geo: string; gender: string; age_from: number; age_to_exclusive: number }
export interface AudienceCatalog { engine_version: string; world_config_digest: string; channels: { channel_id: string; segments: AudienceSegment[] }[] }
const idPattern = /^[a-z][a-z0-9_-]{0,63}$/
export function normalizeAudience(raw: unknown): Audience {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('invalid_audience')
  const entries = Object.entries(raw)
  if (!entries.length || entries.length > 20) throw new Error('invalid_audience')
  return Object.fromEntries(entries.sort(([a], [b]) => a.localeCompare(b)).map(([id, value]) => {
    if (!idPattern.test(id) || !value || typeof value !== 'object' || Array.isArray(value)) throw new Error('invalid_audience')
    const v = value as Record<string, unknown>
    if (Object.keys(v).some(key => !['segment_ids'].includes(key))) throw new Error('invalid_audience')
    if (!Array.isArray(v.segment_ids) || !v.segment_ids.length || v.segment_ids.length > 128 || v.segment_ids.some(s => typeof s !== 'string' || !idPattern.test(s)) || new Set(v.segment_ids).size !== v.segment_ids.length) throw new Error('invalid_audience')
    return [id, { segment_ids: [...v.segment_ids].sort() }]
  }))
}
export function audienceEqual(a: Audience | undefined, b: Audience | undefined): boolean {
  return JSON.stringify(a === undefined ? null : normalizeAudience(a)) === JSON.stringify(b === undefined ? null : normalizeAudience(b))
}
