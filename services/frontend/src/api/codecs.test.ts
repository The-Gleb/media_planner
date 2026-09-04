import { describe, expect, it } from 'vitest'
import { decodeStepResult, decodeWorldMetadata } from './codecs'

describe('API codecs', () => {
  it('decodes only valid world metadata', () => {
    expect(decodeWorldMetadata({ engine_version: 'sim-v0', world_config_digest: 'a'.repeat(64), currency: 'RUB', channel_ids: ['a'] }).channelIds).toEqual(['a'])
    expect(() => decodeWorldMetadata({ engine_version: 'sim-v0', world_config_digest: 'x', currency: 'rub', channel_ids: [] })).toThrow()
  })
  it('preserves decimal strings and converts counts', () => {
    const result = decodeStepResult({ simulation_id: 'demo', step_id: 'id', observed_hour: '2026-09-03T06:00:00Z', next_hour: '2026-09-03T07:00:00Z', status: 'active', remaining_hours: 1, observations: [{ channel_id: 'a', hour: '2026-09-03T06:00:00Z', requests: 2, impressions: 1, unique_reach: 1, clicks: 0, conversions: 0, spend: '0.000001', ecpm: '0.001000' }] })
    expect(result.observations[0].requests).toBe(2n)
    expect(result.observations[0].spend).toBe('0.000001')
  })
})
