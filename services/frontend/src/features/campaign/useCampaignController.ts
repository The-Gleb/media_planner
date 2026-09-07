import { useCallback, useReducer, useRef } from 'react'
import { plannerClient } from '../../api/plannerClient'
import { SimulatorProblemError, simulatorClient } from '../../api/simulatorClient'
import { userError } from '../../app/messages'
import { zeroCampaignFacts } from '../../domain/campaignFacts'
import { sameMarket, savePastCampaigns } from '../../domain/history'
import type { WorldMetadata } from '../../domain/types'
import { activatePlan } from '../planning/activePlan'
import { buildPlanRequest, buildTargetPlanRequest } from '../planning/planRequest'
import { campaignReducer, createCampaignState, type CampaignAction } from './campaignState'
import { validateDraft } from './validation'

const apiFieldPaths: Record<string, string> = {
  simulation_id: 'simulation.simulationId', world_seed: 'simulation.worldSeed',
  campaign_seed: 'simulation.campaignSeed', start_hour: 'simulation.startHour',
  time_zone: 'simulation.timeZone', duration_hours: 'campaign.durationHours',
}

export function useCampaignController(metadata: WorldMetadata) {
  const [state, reactDispatch] = useReducer(campaignReducer, metadata, createCampaignState)
  const ref = useRef(state)
  // Only dispatch advances execution state. React may render a queued snapshot after
  // newer hours have committed; copying that snapshot back would roll the run back.
  // Batched mode: the ref is the source of truth for the run loop; React only receives the
  // accumulated state on flush, so a fast timelapse renders a few times per second instead of
  // two or three times per simulated hour.
  const batchRef = useRef<{ active: boolean; dirty: boolean; flushedAt: number }>({ active: false, dirty: false, flushedAt: 0 })
  const dispatch = useCallback((action: CampaignAction) => {
    ref.current = campaignReducer(ref.current, action)
    if (batchRef.current.active) { batchRef.current.dirty = true; return }
    reactDispatch(action)
  }, [])
  const flush = useCallback(() => {
    if (!batchRef.current.dirty) return
    batchRef.current.dirty = false
    batchRef.current.flushedAt = Date.now()
    reactDispatch({ type: 'replace', state: ref.current })
  }, [])
  const beginBatch = useCallback(() => { batchRef.current = { active: true, dirty: false, flushedAt: Date.now() } }, [])
  const flushIfDue = useCallback((intervalMs: number) => { if (Date.now() - batchRef.current.flushedAt >= intervalMs) flush() }, [flush])
  const endBatch = useCallback(() => { batchRef.current.active = false; flush() }, [flush])

  const createOrReset = useCallback(async () => {
    const current = ref.current
    if (current.busy) return
    const errors = validateDraft(current.draft, metadata)
    if (Object.keys(errors).length) { dispatch({ type: 'invalid', errors }); return }
    const launch = structuredClone(current.draft)
    dispatch({ type: 'begin' })
    try {
      const { simulation, campaign } = launch
      const facts = zeroCampaignFacts(metadata.channelIds)
      const requestId = crypto.randomUUID()
      const history = campaign.useHistory
        ? current.pastCampaigns.filter((record) => sameMarket(record, metadata.worldConfigDigest, simulation.worldSeed)).map((record) => record.payload)
        : []
      const common = { simulation, durationHours: Number(campaign.durationHours), channels: metadata.channelIds,
        currency: metadata.currency, worldConfigDigest: metadata.worldConfigDigest, facts, requestId, history }
      const request = campaign.planType === 'fixed_budget'
        ? buildPlanRequest({ ...common, budget: campaign.totalBudget, optimize: campaign.optimize, strategy: campaign.strategy })
        : buildTargetPlanRequest({ ...common, targetMetric: campaign.targetMetric, targetValue: campaign.targetValue })
      const result = await plannerClient.plan(request)
      if (!result.feasible) {
        dispatch({ type: 'infeasible', diagnosis: result })
        return
      }
      const plan = result
      const activePlan = activatePlan(plan, requestId, 0, metadata.channelIds, undefined, request)
      const activeLaunch = structuredClone(launch)
      activeLaunch.campaign.totalBudget = plan.budget
      activeLaunch.campaign.optimize = plan.optimize
      activeLaunch.campaign.strategy = plan.strategy
      const prior = ref.current.session
      const currentETag = prior?.simulationId === simulation.simulationId ? prior.etag : null
      const response = await simulatorClient.putSimulation(simulation.simulationId, {
        ...(campaign.audience === undefined ? {} : { audience: campaign.audience }),
        world_seed: simulation.worldSeed, campaign_seed: simulation.campaignSeed,
        start_hour: new Date(simulation.startHour).toISOString().replace('.000Z', 'Z'),
        duration_hours: Number(campaign.durationHours), time_zone: simulation.timeZone,
        disable_random_events: simulation.disableRandomEvents,
        scenario_events: simulation.scenario.enabled ? [{
          channel_id: simulation.scenario.channelId, metric: simulation.scenario.metric,
          start_index: Number(simulation.scenario.startIndex), duration_hours: Number(simulation.scenario.durationHours),
          multiplier: simulation.scenario.metric === 'pause' ? 0 : Number(simulation.scenario.multiplier),
        }] : [],
      }, currentETag)
      dispatch({ type: 'created', session: { ...response.data, ...(campaign.audience === undefined ? {} : { audience: structuredClone(campaign.audience) }) }, activeDraft: activeLaunch, activePlan, facts, historyCount: history.length })
      savePastCampaigns(ref.current.pastCampaigns)
    } catch (error) {
      const fieldErrors = error instanceof SimulatorProblemError
        ? Object.fromEntries((error.problem.errors ?? []).map((entry) => [apiFieldPaths[entry.field] ?? entry.field, entry.detail ?? entry.code]))
        : undefined
      dispatch({ type: 'failed', error: userError(error, ref.current.session ? 'Сброс кампании' : 'Создание кампании'), fieldErrors })
    }
  }, [dispatch, metadata])

  const clearHistory = useCallback(() => { dispatch({ type: 'clear-history' }); savePastCampaigns([]) }, [dispatch])

  return { state, dispatch, getState: () => ref.current, createOrReset, clearHistory, beginBatch, flushIfDue, endBatch }
}
