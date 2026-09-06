import { describe, expect, it } from 'vitest'
import { audienceKey } from './audience'
import { sameMarket, type PastCampaignRecord } from './history'

describe('audience history isolation', () => {
  it('ignores channel and segment order', () => {
    expect(audienceKey({ b: { segment_ids: ['y', 'x'] }, a: { segment_ids: ['z'] } })).toBe(audienceKey({ a: { segment_ids: ['z'] }, b: { segment_ids: ['x', 'y'] } }))
  })
  it('does not train a selected audience on broad or different audiences', () => {
    const record = { worldConfigDigest: 'world', worldSeed: '1' } as PastCampaignRecord
    const audience = { a: { segment_ids: ['x'] } }
    expect(sameMarket(record, 'world', '1')).toBe(true)
    expect(sameMarket(record, 'world', '1', audience)).toBe(false)
    expect(sameMarket({ ...record, audience }, 'world', '1', audience)).toBe(true)
    expect(sameMarket({ ...record, audience }, 'world', '1', { a: { segment_ids: ['y'] } })).toBe(false)
  })
})
