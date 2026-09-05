import { describe, expect, it } from 'vitest'
import { aggregateObservations } from '../../domain/aggregates'
import { observation, result } from '../../test/fixtures'
import { chartRows, exactMetricValue, seriesDefinitions } from './metricSeries'

describe('metric series', () => {
  it('adds a stable and explicitly labeled aggregate', () => {
    const definitions = seriesDefinitions(['a', 'b'], 'unique_reach')
    expect(definitions.at(-1)?.label).toContain('без дедупликации')
  })
  it('keeps exact values apart from chart coordinates', () => {
    const value = result()
    value.aggregate = aggregateObservations(value.observations)
    expect(exactMetricValue(value, 'aggregate', 'spend')).toBe('20.000000')
    expect(chartRows([value], ['search_1', 'social_1'], 'requests')[0].aggregate).toBe(200)
  })
  it('derives funnel and cost metrics for channels and aggregate', () => {
    const value = result(); value.aggregate = aggregateObservations(value.observations)
    expect(exactMetricValue(value, 'aggregate', 'ctr')).toBe('10.0000')
    expect(exactMetricValue(value, 'aggregate', 'cr')).toBe('20.0000')
    expect(exactMetricValue(value, 'aggregate', 'cpc')).toBe('2.000000')
    expect(exactMetricValue(value, 'aggregate', 'cpa')).toBe('10.000000')
  })
  it('leaves undefined rates and costs empty when their denominator is zero', () => {
    const value = result({ observations: [observation('search_1', { impressions: 0n, clicks: 0n, conversions: 0n })] })
    value.aggregate = aggregateObservations(value.observations)
    expect(exactMetricValue(value, 'aggregate', 'ctr')).toBeNull()
    expect(exactMetricValue(value, 'aggregate', 'cr')).toBeNull()
    expect(exactMetricValue(value, 'aggregate', 'cpc')).toBeNull()
    expect(exactMetricValue(value, 'aggregate', 'cpa')).toBeNull()
  })
})
