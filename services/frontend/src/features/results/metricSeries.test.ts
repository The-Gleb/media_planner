import { describe, expect, it } from 'vitest'
import { aggregateObservations } from '../../domain/aggregates'
import { result } from '../../test/fixtures'
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
})
