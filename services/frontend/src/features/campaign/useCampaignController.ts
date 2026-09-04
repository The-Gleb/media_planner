import { useCallback, useEffect, useReducer, useRef } from 'react'
import { plannerClient } from '../../api/plannerClient'
import { SimulatorProblemError, simulatorClient } from '../../api/simulatorClient'
import { userError } from '../../app/messages'
import { zeroCampaignFacts } from '../../domain/campaignFacts'
import type { WorldMetadata } from '../../domain/types'
import { activatePlan } from '../planning/activePlan'
import { buildPlanRequest } from '../planning/planRequest'
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
  useEffect(() => { ref.current = state }, [state])
  const dispatch = useCallback((action: CampaignAction) => {
    ref.current = campaignReducer(ref.current, action)
    reactDispatch(action)
  }, [])

  const createOrReset = useCallback(async () => {
    const current = ref.current
    const errors = validateDraft(current.draft, metadata)
    if (Object.keys(errors).length) { dispatch({ type: 'invalid', errors }); return }
    const launch = structuredClone(current.draft)
    if (launch.campaign.planType !== 'fixed_budget') {
      dispatch({ type: 'failed', error: 'Планирование по целевой метрике пока недоступно.' })
      return
    }
    dispatch({ type: 'begin' })
    try {
      const { simulation, campaign } = launch
      const facts = zeroCampaignFacts(metadata.channelIds)
      const requestId = crypto.randomUUID()
      const request = buildPlanRequest({
        simulation, durationHours: Number(campaign.durationHours), channels: metadata.channelIds,
        currency: metadata.currency, worldConfigDigest: metadata.worldConfigDigest,
        budget: campaign.totalBudget, optimize: campaign.optimize, strategy: campaign.strategy,
        facts, requestId,
      })
      const plan = await plannerClient.plan(request)
      const activePlan = activatePlan(plan, requestId, 0, metadata.channelIds, undefined, request)
      const prior = ref.current.session
      const currentETag = prior?.simulationId === simulation.simulationId ? prior.etag : null
      const response = await simulatorClient.putSimulation(simulation.simulationId, {
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
      dispatch({ type: 'created', session: response.data, activeDraft: launch, activePlan, facts })
    } catch (error) {
      const fieldErrors = error instanceof SimulatorProblemError
        ? Object.fromEntries((error.problem.errors ?? []).map((entry) => [apiFieldPaths[entry.field] ?? entry.field, entry.detail ?? entry.code]))
        : undefined
      dispatch({ type: 'failed', error: userError(error, ref.current.session ? 'Сброс кампании' : 'Создание кампании'), fieldErrors })
    }
  }, [dispatch, metadata])

  return { state, dispatch, getState: () => ref.current, createOrReset }
}
