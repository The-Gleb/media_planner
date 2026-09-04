import { lazy, Suspense, useRef, useState } from 'react'
import { simulatorClient } from '../api/simulatorClient'
import type { ExecutionStatus, PendingStep, WorldMetadata } from '../domain/types'
import { CampaignForm } from '../features/campaign/CampaignForm'
import { CampaignSummary } from '../features/campaign/CampaignSummary'
import { ServiceStatus } from '../features/campaign/ServiceStatus'
import { useCampaignController } from '../features/campaign/useCampaignController'
import { runRemaining } from '../features/execution/autoRunController'
import { commitHourlyResult } from '../features/execution/history'
import { createPendingStep, submitPendingStep } from '../features/execution/stepController'
import { RunProgress } from '../features/execution/RunProgress'
import { StepControls } from '../features/execution/StepControls'
import { AllocationTable } from '../features/planning/AllocationTable'
import { buildPlanRequest } from '../features/planning/planRequest'
import { PlanSummary } from '../features/planning/PlanSummary'
import { ReplanningStatus } from '../features/planning/ReplanningStatus'
import { usePlanningController } from '../features/planning/usePlanningController'
import { ActualKPISummary } from '../features/results/ActualKPISummary'
import { LatestObservations } from '../features/results/LatestObservations'
import { StrategyComparison } from '../features/results/StrategyComparison'
import { userError } from './messages'
import { useServicesBootstrap } from './useServicesBootstrap'

const MetricHistory = lazy(() => import('../features/results/MetricHistory').then((module) => ({ default: module.MetricHistory })))

export function App() {
  const bootstrap = useServicesBootstrap()
  return <main className="app-shell stack">
    <header><p className="eyebrow">MEDIA PLANNER · MARKET LAB</p><h1>Планировщик рекламной кампании</h1><p className="lead">Задайте бюджет и горизонт, получите медиаплан и наблюдайте фактический результат по часам.</p></header>
    <ServiceStatus state={bootstrap} onRetry={() => void bootstrap.refresh()} />
    {bootstrap.metadata && <ReadyDashboard key={bootstrap.metadata.worldConfigDigest} metadata={bootstrap.metadata} plannerReady={bootstrap.planner === 'ready'} />}
  </main>
}

function ReadyDashboard({ metadata, plannerReady }: { metadata: WorldMetadata; plannerReady: boolean }) {
  const campaign = useCampaignController(metadata)
  const { state, dispatch, getState, createOrReset } = campaign
  const planning = usePlanningController(metadata.channelIds, dispatch)
  const [execution, setExecution] = useState<ExecutionStatus>('idle')
  const [playbackDelayMs, setPlaybackDelayMs] = useState(500)
  const playbackDelayRef = useRef(playbackDelayMs)
  const stopRef = useRef(false)
  const pendingStepRef = useRef<PendingStep | null>(null)

  function nextPending() {
    const current = getState()
    if (!current.session || !current.activePlan) throw new Error('campaign_missing')
    const prior = pendingStepRef.current
    const pending = prior?.expectedHour === current.session.currentHour
      ? { ...prior, attempt: prior.attempt + 1 }
      : createPendingStep(current.session, current.activePlan)
    pendingStepRef.current = pending
    return pending
  }

  async function commitAndReplan(pending: PendingStep, response: Awaited<ReturnType<typeof submitPendingStep>>) {
    const current = getState()
    if (!current.session || !current.activeDraft || !current.activePlan) throw new Error('campaign_missing')
    const committed = commitHourlyResult(current.history, current.session, current.facts, pending, response.data, response.etag)
    pendingStepRef.current = null
    const request = buildPlanRequest({
      simulation: current.activeDraft.simulation,
      durationHours: Number(current.activeDraft.campaign.durationHours),
      channels: metadata.channelIds,
      currency: metadata.currency,
      worldConfigDigest: metadata.worldConfigDigest,
      budget: current.activePlan.budget,
      optimize: current.activePlan.optimize,
      strategy: current.activePlan.strategy,
      facts: committed.facts,
    })
    const expectedPlanId = current.activePlan.strategy === 'uniform' ? current.activePlan.planId : null
    const round = planning.prepare(request, expectedPlanId, current.activePlan)
    dispatch({ type: 'facts-committed', ...committed, pendingRound: round })
    await planning.submit(round)
  }

  function fail(error: unknown, operation: string) {
    setExecution('error')
    if (getState().planning !== 'replan_failed') dispatch({ type: 'failed', error: userError(error, operation) })
  }

  async function oneHour() {
    const current = getState()
    if (!current.session || current.planning !== 'idle' || ['stepping', 'running', 'stopping'].includes(execution) || current.session.status === 'finished') return
    setExecution('stepping')
    try {
      const pending = nextPending()
      const response = await submitPendingStep(simulatorClient, current.session, pending)
      await commitAndReplan(pending, response)
      setExecution('idle')
    } catch (error) { fail(error, 'Симуляция одного часа') }
  }

  async function runToEnd() {
    const current = getState()
    if (!current.session || current.planning !== 'idle' || ['stepping', 'running', 'stopping'].includes(execution) || current.session.status === 'finished') return
    stopRef.current = false
    setExecution('running')
    try {
      const outcome = await runRemaining({
        getSession: () => { const session = getState().session; if (!session) throw new Error('campaign_missing'); return session },
        createPending: () => nextPending(),
        submit: (session, pending) => submitPendingStep(simulatorClient, session, pending),
        commit: commitAndReplan,
        shouldStop: () => stopRef.current,
        waitBeforeNext: async () => {
          const delay = playbackDelayRef.current
          if (delay > 0) await new Promise((resolve) => setTimeout(resolve, delay))
        },
      })
      setExecution(outcome === 'stopped' ? 'stopped' : 'idle')
    } catch (error) { fail(error, 'Автоматический прогон') }
  }

  async function retryReplan() {
    try { await planning.retry(); setExecution('idle') } catch { setExecution('error') }
  }

  const blocked = !plannerReady || state.planning !== 'idle'
  const mutating = state.busy || blocked || ['stepping', 'running', 'stopping'].includes(execution)
  return <>
    <ActualKPISummary facts={state.facts} currency={metadata.currency} finished={state.session?.status === 'finished'} />
    <CampaignForm metadata={metadata} draft={state.draft} errors={state.fieldErrors} busy={mutating} hasSession={Boolean(state.session)} onChange={(draft) => dispatch({ type: 'draft', draft })} onSubmit={() => { pendingStepRef.current = null; setExecution('idle'); void createOrReset() }} />
    {state.error && <section className="operation-error" role="alert"><strong>Операция не выполнена</strong><p>{state.error}</p></section>}
    <ReplanningStatus status={state.planning} onRetry={() => void retryReplan()} />
    {state.completedRuns.length > 0 && state.activeDraft && <StrategyComparison previous={state.completedRuns.at(-1)!} current={{ strategy: state.activeDraft.campaign.strategy, optimize: state.activeDraft.campaign.optimize, facts: state.facts, finished: state.session?.status === 'finished' }} />}
    {state.session && state.activeDraft && state.activePlan && <>
      <PlanSummary plan={state.activePlan} />
      <AllocationTable plan={state.activePlan} currentHour={state.facts.currentHour} />
      <CampaignSummary session={state.session} activeDraft={state.activeDraft} />
      <section className="card stack timelapse-player" aria-labelledby="control-title"><div className="status-line"><div><p className="eyebrow">TIMELAPSE</p><h2 id="control-title">Ход кампании</h2></div><span className="status-badge" data-tone={execution === 'running' ? 'ok' : undefined}>{execution === 'running' ? 'В эфире' : state.session.status === 'finished' ? 'Завершена' : 'Ожидает'}</span></div><RunProgress session={state.session} status={execution} /><StepControls session={state.session} status={execution} blocked={blocked} playbackDelayMs={playbackDelayMs} onPlaybackDelayChange={(delay) => { playbackDelayRef.current = delay; setPlaybackDelayMs(delay) }} onStep={() => void oneHour()} onRun={() => void runToEnd()} onStop={() => { stopRef.current = true; setExecution('stopping') }} /></section>
      {state.history.length > 0 && <Suspense fallback={<section className="card" aria-busy="true">Подготовка графика…</section>}><MetricHistory history={state.history} channelIds={state.session.channelIds} currency={state.session.currency} timeZone={state.session.timeZone} running={execution === 'running' || execution === 'stopping'} /></Suspense>}
      {state.history.length > 0 && <LatestObservations result={state.history.at(-1)!} currency={state.session.currency} />}
    </>}
  </>
}
