import { describe, expect, it } from 'vitest'
import { aggregateObservations } from './aggregates'
import { observation } from '../test/fixtures'

describe('hourly aggregates', () => {
  it('sums counts, spend and computes weighted eCPM', () => {
    const aggregate = aggregateObservations([
      observation('a', { impressions: 3n, requests: 10n, uniqueReach: 2n, spend: '0.000001', ecpm: '0.000334' }),
      observation('b', { impressions: 0n, requests: 7n, uniqueReach: 0n, clicks: 0n, conversions: 0n, spend: '0', ecpm: null }),
    ])
    expect(aggregate.requests).toBe(17n)
    expect(aggregate.uniqueReach).toBe(2n)
    expect(aggregate.spend).toBe('0.000001')
    expect(aggregate.ecpm).toBe('0.000334')
  })
})
