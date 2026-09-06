import { describe, expect, it } from 'vitest'
import { initialDraft } from '../campaign/validation'
import { facts, metadata, result, session } from '../../test/fixtures'
import { applyCompletionPolicy, remainingBudgetActions } from './completionPolicy'
import { runRemaining } from './autoRunController'
import type { ActiveRun } from '../../domain/types'

const campaign = { ...initialDraft(metadata).campaign, planType: 'target_kpi' as const, totalBudget: '100', targetValue: '10' }

describe('target KPI completion policy', () => {
  it.each(['clicks', 'conversions', 'unique_reach'] as const)('stops at actual %s target', metric => {
    const draft = { ...campaign, targetMetric: metric }
    const key = metric === 'unique_reach' ? 'uniqueReach' : metric
    expect(applyCompletionPolicy(session, draft, { ...facts, [key]: '9' })).toBe(session)
    for (const value of ['10', '11']) expect(applyCompletionPolicy(session, draft, { ...facts, [key]: value })).toMatchObject({ status: 'finished', completionReason: 'kpi_reached', remainingHours: 2 })
  })
  it('does not apply a target stop to fixed budget campaigns', () => {
    expect(applyCompletionPolicy(session, { ...campaign, planType: 'fixed_budget' }, { ...facts, clicks: '15' })).toBe(session)
  })
  it('offers the entire remaining budget in the final hour', () => {
    const actions = [{ channelId: 'search_1', budgetCap: '3' }, { channelId: 'social_1', budgetCap: '1' }]
    expect(remainingBudgetActions(actions, { ...session, remainingHours: 1 }, { ...campaign, kpiCompletionPolicy: 'spend_budget' }, { ...facts, clicks: '10', spent: '20' })).toEqual([
      { channelId: 'search_1', budgetCap: '60.000000' }, { channelId: 'social_1', budgetCap: '20.000000' },
    ])
  })
  it.each(['stop_at_kpi', 'spend_budget'] as const)('autorun obeys %s at the commit boundary', async policy => {
    let current: ActiveRun = session
    let steps = 0
    const outcome = await runRemaining({
      getSession: () => current,
      createPending: () => ({ stepId: 'id', expectedHour: current.currentHour, actions: [], etag: null, attempt: 1 }),
      submit: async () => { steps++; return { data: result(), etag: null } },
      commit: () => { current = applyCompletionPolicy({ ...current, remainingHours: 2 - steps }, { ...campaign, kpiCompletionPolicy: policy }, { ...facts, clicks: '12', spent: steps === 1 ? '20' : '100' }) },
      shouldStop: () => false,
    })
    expect(outcome).toBe('finished')
    expect(steps).toBe(policy === 'stop_at_kpi' ? 1 : 2)
    expect(current.completionReason).toBe(policy === 'stop_at_kpi' ? 'kpi_reached' : 'budget_spent')
  })
})
