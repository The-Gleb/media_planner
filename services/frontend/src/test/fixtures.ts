import type { ActiveRun, HourlyResult, Observation, WorldMetadata } from '../domain/types'
import type { ActivePlan, MediaPlan } from '../domain/planning'
import { zeroCampaignFacts } from '../domain/campaignFacts'

export const metadata: WorldMetadata = {
  engineVersion: 'sim-v0', worldConfigDigest: 'a'.repeat(64), currency: 'RUB', channelIds: ['search_1', 'social_1'],
}

export const session: ActiveRun = {
  simulationId: 'demo', status: 'active', currentHour: '2026-09-03T06:00:00Z', endHourExclusive: '2026-09-03T08:00:00Z',
  durationHours: 2, remainingHours: 2, timeZone: 'Europe/Moscow', currency: 'RUB', engineVersion: 'sim-v0', worldConfigDigest: 'a'.repeat(64), channelIds: metadata.channelIds, etag: '"1-aaaaaaaaaaaaaaaa"',
}

export function observation(channelId: string, overrides: Partial<Observation> = {}): Observation {
  return { channelId, hour: '2026-09-03T06:00:00Z', requests: 100n, impressions: 50n, uniqueReach: 40n, clicks: 5n, conversions: 1n, spend: '10.000000', ecpm: '200.000000', ...overrides }
}

export function result(overrides: Partial<HourlyResult> = {}): HourlyResult {
  return { simulationId: 'demo', stepId: '00000000-0000-4000-8000-000000000001', observedHour: '2026-09-03T06:00:00Z', nextHour: '2026-09-03T07:00:00Z', status: 'active', remainingHours: 1, observations: [observation('search_1'), observation('social_1')], ...overrides }
}
export const facts = zeroCampaignFacts(metadata.channelIds)
export function mediaPlan(overrides: Partial<MediaPlan> = {}): MediaPlan {
  return { requestId: '00000000-0000-4000-8000-000000000010', stateRevision: 0, planId: 'b'.repeat(64), feasible: true, type: 'fixed_budget', strategy: 'uniform', optimize: 'unique_reach', currency: 'RUB', budget: '12.000000', horizon: { fromHour: 0, toHour: 2 }, expected: null, allocations: [
    { channelId: 'search_1', hour: 0, budgetCap: '3.000000', expected: null }, { channelId: 'social_1', hour: 0, budgetCap: '3.000000', expected: null },
    { channelId: 'search_1', hour: 1, budgetCap: '3.000000', expected: null }, { channelId: 'social_1', hour: 1, budgetCap: '3.000000', expected: null },
  ], unallocatedBudget: '0.000000', requiredBudget: null, reason: null, target: null, ...overrides }
}
export function activePlan(overrides: Partial<MediaPlan> = {}): ActivePlan {
  const plan = mediaPlan(overrides), index = new Map<number, ReadonlyMap<string, string>>()
  for (const allocation of plan.allocations) { const row = new Map(index.get(allocation.hour) ?? []); row.set(allocation.channelId, allocation.budgetCap); index.set(allocation.hour, row) }
  return { ...plan, index }
}
