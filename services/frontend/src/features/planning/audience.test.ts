import { describe, it, expect } from 'vitest'
import { normalizeAudience, audienceEqual } from '../../domain/audience'
import { activatePlan } from './activePlan'
import { activePlan, session } from '../../test/fixtures'
import { createPendingStep, retryPendingStep } from '../execution/stepController'

describe('fixed audience context', () => {
  it('normalizes copies and rejects null, empty and duplicates', () => {
    const raw = { social_1: { segment_ids: ['b', 'a'] } }
    const value = normalizeAudience(raw)
    raw.social_1.segment_ids[0] = 'changed'
    expect(value.social_1).toEqual({ segment_ids: ['a', 'b'] })
    expect(audienceEqual(value, normalizeAudience({ social_1: { segment_ids: ['b', 'a'] } }))).toBe(true)
    for (const bad of [null, {}, { a: { segment_ids: [] } }, { a: { segment_ids: ['x', 'x'] } }]) expect(() => normalizeAudience(bad)).toThrow()
  })
  it('takes an owned step snapshot and preserves it on retry', () => {
    const run = { ...session, audience: normalizeAudience({ social_1: { segment_ids: ['a'] } }) }
    const pending = createPendingStep(run, activePlan())
    run.audience.social_1.segment_ids[0] = 'changed'
    expect(pending.audience?.social_1.segment_ids).toEqual(['a'])
    expect(retryPendingStep(pending).audience).toBe(pending.audience)
  })
  it('accepts a legacy plan without any audience echo', () => {
    const plan = activePlan()
    expect(() => activatePlan(plan, plan.requestId, plan.stateRevision, session.channelIds)).not.toThrow()
  })
})
