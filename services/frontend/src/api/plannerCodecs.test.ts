import { describe, expect, it } from 'vitest'
import { decodeMediaPlan, validatePlanCoverage } from './plannerCodecs'

const raw = () => ({
  request_id: '00000000-0000-4000-8000-000000000010', state_revision: 0,
  plan_id: 'b'.repeat(64), feasible: true, type: 'fixed_budget', strategy: 'uniform',
  optimize: 'unique_reach', currency: 'RUB', budget: '12.000000',
  horizon: { from_hour: 0, to_hour: 2 }, expected: null,
  allocations: [
    { channel_id: 'search_1', hour: 0, budget_cap: '3.000000', expected: null },
    { channel_id: 'social_1', hour: 0, budget_cap: '3.000000', expected: null },
    { channel_id: 'search_1', hour: 1, budget_cap: '3.000000', expected: null },
    { channel_id: 'social_1', hour: 1, budget_cap: '3.000000', expected: null },
  ], required_budget: null, reason: null,
})

describe('planner codecs', () => {
  it('preserves canonical exact strings and validates complete coverage', () => {
    const plan = decodeMediaPlan(raw())
    validatePlanCoverage(plan, ['search_1', 'social_1'])
    expect(plan.budget).toBe('12.000000')
    expect(plan.allocations.map((item) => item.budgetCap)).toEqual(Array(4).fill('3.000000'))
  })
  it('accepts optimized strategy', () => {
    const value = raw()
    value.strategy = 'optimized'
    expect(decodeMediaPlan(value).strategy).toBe('optimized')
  })
  it.each([
    ['noncanonical money', (value: unknown) => { (value as { budget: string }).budget = '12' }],
    ['extra field', (value: unknown) => { (value as Record<string, unknown>).extra = true }],
    ['wrong null', (value: unknown) => { (value as Record<string, unknown>).expected = 0 }],
    ['wrong order', (value: unknown) => { (value as { allocations: unknown[] }).allocations.reverse() }],
  ])('rejects %s', (_, change) => {
    const value = raw(); change(value); expect(() => decodeMediaPlan(value)).toThrow()
  })
  it('rejects missing pairs and inexact sum', () => {
    const value = raw(); value.allocations[0].budget_cap = '2.000000'
    expect(() => validatePlanCoverage(decodeMediaPlan(value), ['search_1', 'social_1'])).toThrow('invalid_plan_total')
  })
})
