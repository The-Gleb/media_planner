import { describe, expect, it } from 'vitest'
import { currentDeviation, hasTrajectory, planTrajectory } from './planTrajectory'
import { activePlan, observation, result } from '../../test/fixtures'
import { aggregateObservations } from '../../domain/aggregates'

const expected = (spend: string, clicks: string) => ({ spend, impressions: '100', uniqueReach: '10', clicks, conversions: '1' })
const plan = activePlan({
  optimize: 'clicks',
  allocations: [
    { channelId: 'search_1', hour: 0, budgetCap: '3.000000', expected: expected('3.000000', '2.5') }, { channelId: 'social_1', hour: 0, budgetCap: '3.000000', expected: expected('3.000000', '2.5') },
    { channelId: 'search_1', hour: 1, budgetCap: '3.000000', expected: expected('3.000000', '2.5') }, { channelId: 'social_1', hour: 1, budgetCap: '3.000000', expected: expected('3.000000', '2.5') },
  ],
})

describe('plan trajectory', () => {
  it('accumulates the approved plan and the fact hour by hour', () => {
    const observations = [observation('search_1', { clicks: 4n, spend: '2.000000' }), observation('social_1', { clicks: 3n, spend: '2.500000' })]
    const history = [{ ...result({ observations }), aggregate: aggregateObservations(observations) }]
    const points = planTrajectory(plan, history, 'clicks')
    expect(points).toEqual([
      { hour: 1, planSpend: 6, planKpi: 5, factSpend: 4.5, factKpi: 7 },
      { hour: 2, planSpend: 12, planKpi: 10, factSpend: null, factKpi: null },
    ])
    const deviation = currentDeviation(points, 1)
    expect(deviation?.hour).toBe(1)
    expect(deviation?.spend).toBeCloseTo(-0.25, 10)
    expect(deviation?.kpi).toBeCloseTo(0.4, 10)
    expect(currentDeviation(points, 0)).toBeNull()
    expect(hasTrajectory(plan)).toBe(true)
    expect(hasTrajectory(activePlan())).toBe(false)
  })
})
