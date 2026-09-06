import type { AudienceCatalog } from '../domain/audience'
export function decodeAudienceCatalog(raw: unknown): AudienceCatalog {
  const v = raw as AudienceCatalog
  if (!v || typeof v.engine_version !== 'string' || !/^[a-f0-9]{64}$/.test(v.world_config_digest) || !Array.isArray(v.channels) || !v.channels.length || v.channels.length > 20) throw new Error('invalid_audience_catalog')
  const ids = new Set<string>()
  for (const c of v.channels) {
    if (!c || !/^[a-z][a-z0-9_-]{0,63}$/.test(c.channel_id) || ids.has(c.channel_id) || !Array.isArray(c.segments) || c.segments.length > 128) throw new Error('invalid_audience_catalog')
    ids.add(c.channel_id)
    const segments = new Set<string>()
    for (const s of c.segments) {
      if (!s || !/^[a-z][a-z0-9_-]{0,63}$/.test(s.segment_id) || segments.has(s.segment_id) || typeof s.geo !== 'string' || !s.geo || typeof s.gender !== 'string' || !s.gender || !Number.isInteger(s.age_from) || !Number.isInteger(s.age_to_exclusive) || s.age_from < 0 || s.age_to_exclusive <= s.age_from || s.age_to_exclusive > 131) throw new Error('invalid_audience_catalog')
      segments.add(s.segment_id)
    }
  }
  return v
}
