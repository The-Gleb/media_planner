import { describe, expect, it } from 'vitest'
import type { HourlyResult, Observation } from '../../domain/types'
import { aggregateObservations } from '../../domain/aggregates'
import { chartRows } from './metricSeries'

describe('maximum history projection', () => {
  it('projects 20 channels by 2160 hours inside the acceptance budget', () => {
    const channels = Array.from({ length: 20 }, (_, index) => `channel_${index}`)
    const history: HourlyResult[] = Array.from({ length: 2160 }, (_, hour) => {
      const observedHour = new Date(Date.UTC(2026, 0, 1, hour)).toISOString().replace('.000Z', 'Z')
      const observations: Observation[] = channels.map((channelId) => ({ channelId, hour: observedHour, requests: 100n, impressions: 50n, uniqueReach: 30n, clicks: 5n, conversions: 1n, spend: '10.000000', ecpm: '200.000000' }))
      return { simulationId: 'scale', stepId: String(hour), observedHour, nextHour: new Date(Date.UTC(2026, 0, 1, hour + 1)).toISOString().replace('.000Z', 'Z'), status: hour === 2159 ? 'finished' : 'active', remainingHours: 2159 - hour, observations, aggregate: aggregateObservations(observations) }
    })
    const started = performance.now()
    for (const metric of ['requests', 'impressions', 'unique_reach', 'clicks', 'conversions', 'spend', 'ecpm'] as const) chartRows(history, channels, metric)
    expect(performance.now() - started).toBeLessThan(3000)
  }, 10_000)
})
