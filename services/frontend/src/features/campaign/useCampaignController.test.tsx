import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { activePlan, facts, mediaPlan, metadata, session } from '../../test/fixtures'
import { initialDraft } from './validation'
import { useCampaignController } from './useCampaignController'
import { plannerClient } from '../../api/plannerClient'
import { simulatorClient } from '../../api/simulatorClient'

afterEach(() => vi.restoreAllMocks())

function setup() {
  const hook = renderHook(() => useCampaignController(metadata))
  act(() => hook.result.current.dispatch({ type: 'created', session, activeDraft: initialDraft(metadata), activePlan: activePlan(), facts }))
  return hook
}

describe('batched campaign state', () => {
  it('never rolls execution back when React renders an older snapshot', () => {
    const { result } = setup()
    act(() => {
      result.current.beginBatch()
      result.current.dispatch({ type: 'facts-committed', session: { ...session, remainingHours: 1 }, history: [], facts: { ...facts, currentHour: 1 }, pendingRound: null })
      result.current.flushIfDue(0)
      // A fast response arrives while the UI update is still queued.
      result.current.dispatch({ type: 'facts-committed', session: { ...session, remainingHours: 0, status: 'finished' }, history: [], facts: { ...facts, currentHour: 2 }, pendingRound: null })
    })
    expect(result.current.state.facts.currentHour).toBe(1)
    expect(result.current.getState().facts.currentHour).toBe(2)
    expect(result.current.getState().session?.status).toBe('finished')
    act(() => result.current.endBatch())
    expect(result.current.state.facts.currentHour).toBe(2)
    expect(result.current.state).toBe(result.current.getState())
  })

  it('preserves a newer plan across a queued render and an error after batching', () => {
    const { result } = setup()
    const nextPlan = activePlan({ stateRevision: 1 })
    act(() => {
      result.current.beginBatch()
      result.current.dispatch({ type: 'clear-error' })
      result.current.flushIfDue(0)
      result.current.dispatch({ type: 'replanned', activePlan: nextPlan })
    })
    expect(result.current.getState().activePlan).toBe(nextPlan)
    act(() => {
      result.current.endBatch()
      result.current.dispatch({ type: 'failed', error: 'test failure' })
    })
    expect(result.current.state.activePlan).toBe(nextPlan)
    expect(result.current.state.error).toBe('test failure')
    expect(result.current.getState()).toEqual(result.current.state)
  })
})


describe('audience launch', () => {
  it('sends the selected segments to the simulator and freezes them in the active draft', async () => {
    const audience = { search_1: { segment_ids: ['moscow_female_25_34'] } }
    vi.spyOn(plannerClient, 'plan').mockImplementation(async request => mediaPlan({ requestId: request.request_id }))
    const create = vi.spyOn(simulatorClient, 'putSimulation').mockResolvedValue({ data: session, etag: session.etag })
    const { result } = renderHook(() => useCampaignController(metadata))
    const draft = initialDraft(metadata)
    draft.campaign.audience = audience
    draft.campaign.durationHours = '2'
    draft.campaign.strategy = 'uniform'
    draft.campaign.totalBudget = '12'
    draft.campaign.optimize = 'unique_reach'
    act(() => result.current.dispatch({ type: 'draft', draft }))
    await act(() => result.current.createOrReset())
    expect(result.current.state.error).toBeNull()
    expect(create).toHaveBeenCalledWith(draft.simulation.simulationId, expect.objectContaining({ audience }), null)
    expect(result.current.state.activeDraft?.campaign.audience).toEqual(audience)
    expect(result.current.state.session?.audience).toEqual(audience)
    act(() => result.current.dispatch({ type: 'draft', draft: { ...draft, campaign: { ...draft.campaign, audience: undefined } } }))
    expect(result.current.state.activeDraft?.campaign.audience).toEqual(audience)
    expect(result.current.state.session?.audience).toEqual(audience)
  })
})
