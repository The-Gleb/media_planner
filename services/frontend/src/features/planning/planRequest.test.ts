import { describe, expect, it } from 'vitest'
import { facts, metadata } from '../../test/fixtures'
import { initialDraft } from '../campaign/validation'
import { buildPlanRequest, buildTargetPlanRequest } from './planRequest'

const common = () => ({
  simulation: { ...initialDraft(metadata).simulation, startHour: '2026-09-03T06:00:00Z' },
  durationHours: 24,
  channels: metadata.channelIds,
  currency: 'RUB',
  worldConfigDigest: metadata.worldConfigDigest,
  facts,
  requestId: '00000000-0000-4000-8000-000000000010',
})

describe('plan request', () => {
  it('uses [0,duration) and the exact same committed KPI facts', () => {
    const committed = { ...facts, currentHour: 1, stateRevision: 1, spent: '1.000001', uniqueReach: '9', clicks: '4', conversions: '2' }
    const request = buildPlanRequest({ ...common(), budget: '12', optimize: 'clicks', facts: committed })
    expect(request.horizon).toEqual({ from_hour: 0, to_hour: 24 })
    expect(request.current).toMatchObject({ state_revision: 1, spent: '1.000001', unique_reach: '9', clicks: '4', conversions: '2' })
    expect(request.market).toEqual({ status: 'unavailable' })
    const targeted = buildPlanRequest({ ...common(), budget: '12', optimize: 'clicks', audience: { social_1: { segment_ids: ['example'] } } })
    expect(targeted).not.toHaveProperty('audience')
  })

  it('builds an initial optimized target request without a user budget', () => {
    const request = buildTargetPlanRequest({ ...common(), targetMetric: 'conversions', targetValue: '5000' })
    expect(request).toMatchObject({ type: 'target_kpi', strategy: 'optimized', budget: null, optimize: null, target: { metric: 'conversions', value: '5000' } })
  })
})
