import { act, renderHook } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { plannerClient } from '../../api/plannerClient'
import { activePlan, facts, metadata } from '../../test/fixtures'
import { initialDraft } from '../campaign/validation'
import { buildPlanRequest } from './planRequest'
import { usePlanningController } from './usePlanningController'
import type { MediaPlan } from '../../domain/planning'

it('does not apply a response from an invalidated run after reset', async () => {
  let resolve!: (plan: MediaPlan) => void
  vi.spyOn(plannerClient, 'plan').mockImplementation(() => new Promise<MediaPlan>(r => { resolve = r }))
  const dispatch = vi.fn()
  const { result } = renderHook(() => usePlanningController(metadata.channelIds, dispatch))
  const request = buildPlanRequest({ simulation: initialDraft(metadata).simulation, durationHours: 2, channels: metadata.channelIds, currency: 'RUB', worldConfigDigest: metadata.worldConfigDigest, budget: '12', optimize: 'clicks', facts })
  const round = result.current.prepare(request, null)
  const pending = result.current.submit(round).catch(error => error)
  act(() => result.current.invalidate())
  resolve(activePlan())
  expect(await pending).toMatchObject({ message: 'stale_plan' })
  expect(dispatch).not.toHaveBeenCalled()
  vi.restoreAllMocks()
})
