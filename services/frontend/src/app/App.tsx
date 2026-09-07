import { useRef, useState } from 'react'
import { simulatorClient } from '../api/simulatorClient'
import type { ExecutionStatus, PendingStep, WorldMetadata } from '../domain/types'
import { useCampaignController } from '../features/campaign/useCampaignController'
import { applyCompletionPolicy, remainingBudgetActions, targetReached } from '../features/execution/completionPolicy'
import { runRemaining } from '../features/execution/autoRunController'
import { commitHourlyResult } from '../features/execution/history'
import { createPendingStep, submitPendingStep } from '../features/execution/stepController'
import { buildPlanRequest } from '../features/planning/planRequest'
import { ReplanningStatus } from '../features/planning/ReplanningStatus'
import { usePlanningController } from '../features/planning/usePlanningController'
import { userError } from './messages'
import { useServicesBootstrap, type ServiceBootstrap } from './useServicesBootstrap'
import { buildApprovedPayload, buildRecentHours, sameMarket, savePastCampaigns } from '../domain/history'
import { BriefStep } from '../features/brief/BriefStep'
import { InfeasibleDiagnosis, PlanStep } from '../features/plan/PlanStep'
import { CampaignStep } from '../features/run/CampaignStep'
import { WorldTab } from '../features/world/WorldTab'
import { useViewMode, ViewModeProvider, ViewModeToggle } from './viewMode'

type Step = 'brief' | 'plan' | 'run' | 'world'

const BATCH_FLUSH_MS = 300

export function App() {
  return <ViewModeProvider><Shell /></ViewModeProvider>
}

function Shell() {
  const bootstrap = useServicesBootstrap()
  const [step, setStep] = useState<Step>('brief')
  return <div className="app">
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand"><span className="brand-mark" aria-hidden="true">MP</span><div><strong>MediaPlan Optimizer</strong><span className="muted">Медиаплан → почасовое ведение кампании на симуляторе рынка</span></div></div>
        <div className="topbar-right"><ServiceChips state={bootstrap} onRetry={() => void bootstrap.refresh()} /><ViewModeToggle /></div>
      </div>
    </header>
    <main className="app-shell stack">
      {!bootstrap.metadata && <section className="card"><h2>Подключение к сервисам</h2><p className="muted">{bootstrap.simulator === 'checking' || bootstrap.planner === 'checking' ? 'Проверяем симулятор и планировщик…' : 'Симулятор или планировщик недоступны. Проверьте, что стек запущен, и повторите.'}</p>{(bootstrap.simulator === 'unavailable' || bootstrap.planner === 'unavailable') && <button type="button" className="secondary" onClick={() => void bootstrap.refresh()}>Повторить</button>}</section>}
      {bootstrap.metadata && <ReadyDashboard key={bootstrap.metadata.worldConfigDigest} metadata={bootstrap.metadata} plannerReady={bootstrap.planner === 'ready'} step={step} setStep={setStep} />}
    </main>
    <footer className="foot muted">Каналы абстрактные, данные синтетические. Прототип планирования и управления темпом расходования бюджета, не система закупок.</footer>
  </div>
}

function ServiceChips({ state, onRetry }: { state: ServiceBootstrap; onRetry: () => void }) {
  const chip = (name: string, status: ServiceBootstrap['planner']) => <span className="chip chip-dot" data-tone={status === 'ready' ? 'ok' : status === 'unavailable' ? 'bad' : undefined} title={`${name}: ${status === 'ready' ? 'готов' : status === 'checking' ? 'проверка' : 'недоступен'}`}>{name}</span>
  return <div className="chips" aria-label="Сервисы">{chip('Симулятор', state.simulator)}{chip('Планировщик', state.planner)}{(state.simulator === 'unavailable' || state.planner === 'unavailable') && <button type="button" className="link-button" onClick={onRetry}>повторить</button>}</div>
}

function Stepper({ step, setStep, planReady, runReady, expert }: { step: Step; setStep: (step: Step) => void; planReady: boolean; runReady: boolean; expert: boolean }) {
  const items: { id: Step; n: string; title: string; who: string; enabled: boolean }[] = [
    { id: 'brief', n: '1', title: 'Бриф', who: 'медиапланер', enabled: true },
    { id: 'plan', n: '2', title: 'Медиаплан', who: 'утверждение', enabled: planReady },
    { id: 'run', n: '3', title: 'Кампания', who: 'трафик-менеджер', enabled: runReady },
  ]
  if (expert) items.push({ id: 'world', n: '◎', title: 'Мир и модели', who: 'для экспертов', enabled: true })
  return <nav className="stepper" aria-label="Шаги">{items.map((item) => <button key={item.id} type="button" className="step" aria-current={step === item.id ? 'step' : undefined} disabled={!item.enabled} onClick={() => setStep(item.id)}><span className="step-n">{item.n}</span><span className="step-text"><strong>{item.title}</strong><span>{item.who}</span></span></button>)}</nav>
}

function ReadyDashboard({ metadata, plannerReady, step, setStep }: { metadata: WorldMetadata; plannerReady: boolean; step: Step; setStep: (step: Step) => void }) {
  const { expert } = useViewMode()
  const campaign = useCampaignController(metadata)
  const { state, dispatch, getState, createOrReset, clearHistory, beginBatch, flushIfDue, endBatch } = campaign
  const marketHistory = state.pastCampaigns.filter((record) => sameMarket(record, metadata.worldConfigDigest, state.draft.simulation.worldSeed))
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
    if (prior?.expectedHour !== current.session.currentHour && current.activeDraft) pending.actions = remainingBudgetActions(pending.actions, current.session, current.activeDraft.campaign, current.facts)
    pendingStepRef.current = pending
    return pending
  }

  async function commitAndReplan(pending: PendingStep, response: Awaited<ReturnType<typeof submitPendingStep>>) {
    const current = getState()
    if (!current.session || !current.activeDraft || !current.activePlan) throw new Error('campaign_missing')
    const committed = commitHourlyResult(current.history, current.session, current.facts, pending, response.data, response.etag)
    committed.session = applyCompletionPolicy(committed.session, current.activeDraft.campaign, committed.facts)
    pendingStepRef.current = null
    const { execution: mode, useHistory } = current.activeDraft.campaign
    const spendRemainder = current.activeDraft.campaign.planType === 'target_kpi' && current.activeDraft.campaign.kpiCompletionPolicy === 'spend_budget' && targetReached(current.activeDraft.campaign, committed.facts)
    if ((mode === 'frozen' && !spendRemainder) || committed.session.status === 'finished') {
      dispatch({ type: 'facts-committed', ...committed, pendingRound: null })
      if (committed.session.status === 'finished') savePastCampaigns(getState().pastCampaigns)
      return
    }
    const history = useHistory
      ? current.pastCampaigns.filter((record) => sameMarket(record, metadata.worldConfigDigest, current.activeDraft!.simulation.worldSeed)).map((record) => record.payload)
      : []
    const tracking = !spendRemainder && mode === 'adaptive' && current.activePlan.strategy === 'optimized' && current.approvedPlan
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
      history,
      recentHours: buildRecentHours(committed.history, metadata.channelIds),
      approved: tracking ? buildApprovedPayload(current.approvedPlan!) : null,
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
    // Without a playback delay the screen is refreshed a few times per second, not every hour.
    const batched = playbackDelayRef.current === 0
    if (batched) beginBatch()
    try {
      const outcome = await runRemaining({
        getSession: () => { const session = getState().session; if (!session) throw new Error('campaign_missing'); return session },
        createPending: () => nextPending(),
        submit: (session, pending) => submitPendingStep(simulatorClient, session, pending),
        commit: async (pending, response) => { await commitAndReplan(pending, response); if (batched) flushIfDue(BATCH_FLUSH_MS) },
        shouldStop: () => stopRef.current,
        waitBeforeNext: async () => {
          const delay = playbackDelayRef.current
          if (delay > 0) await new Promise((resolve) => setTimeout(resolve, delay))
        },
      })
      if (batched) endBatch()
      setExecution(outcome === 'stopped' ? 'stopped' : 'idle')
    } catch (error) { if (batched) endBatch(); fail(error, 'Автоматический прогон') }
  }

  async function retryReplan() {
    try { await planning.retry(); setExecution('idle') } catch { setExecution('error') }
  }

  async function submitBrief() {
    planning.invalidate()
    pendingStepRef.current = null
    setExecution('idle')
    await createOrReset()
    const after = getState()
    if (after.activePlan && !after.error && after.planning === 'idle' && Object.keys(after.fieldErrors).length === 0) setStep('plan')
    else if (after.diagnosis) setStep('plan')
  }

  function acceptRecommendedTarget() {
    const { draft, diagnosis } = getState()
    if (!diagnosis) return
    dispatch({ type: 'draft', draft: { ...draft, campaign: { ...draft.campaign, targetValue: diagnosis.reason.recommendedTarget } } })
    void submitBrief()
  }

  function extendHorizon() {
    const { draft } = getState()
    dispatch({ type: 'draft', draft: { ...draft, campaign: { ...draft.campaign, durationHours: String(Number(draft.campaign.durationHours) + 168) } } })
    void submitBrief()
  }

  const blocked = !plannerReady || state.planning !== 'idle'
  const mutating = state.busy || blocked || ['stepping', 'running', 'stopping'].includes(execution)
  const planReady = Boolean(state.activePlan) || Boolean(state.diagnosis)
  const runReady = Boolean(state.session && state.activeDraft && state.activePlan && state.approvedPlan)
  const sessionStarted = state.history.length > 0

  return <>
    <Stepper step={step} setStep={setStep} planReady={planReady} runReady={runReady} expert={expert} />
    {state.error && <section className="operation-error" role="alert"><strong>Операция не выполнена</strong><p>{state.error}</p></section>}
    <ReplanningStatus status={state.planning} onRetry={() => void retryReplan()} />

    {step === 'brief' && <BriefStep metadata={metadata} draft={state.draft} errors={state.fieldErrors} busy={mutating} hasSession={Boolean(state.session)} pastCampaigns={marketHistory} onClearHistory={clearHistory} onChange={(draft) => dispatch({ type: 'draft', draft })} onSubmit={() => void submitBrief()} />}

    {step === 'plan' && state.activeDraft?.campaign.audience && !state.diagnosis && <p className="note">Показы будут ограничены выбранными сегментами аудитории. Первоначальный прогноз рассчитан по каналам в целом и пока не учитывает это ограничение.</p>}
    {step === 'plan' && state.diagnosis && <InfeasibleDiagnosis diagnosis={state.diagnosis} currency={metadata.currency} onAcceptTarget={acceptRecommendedTarget} onExtendHorizon={extendHorizon} onEdit={() => setStep('brief')} />}
    {step === 'plan' && !state.diagnosis && state.approvedPlan && state.activeDraft && <PlanStep plan={state.approvedPlan} execution={state.activeDraft.campaign.execution} historyCount={state.historyCount} currency={metadata.currency} channelIds={metadata.channelIds} hasSession={Boolean(state.session)} sessionStarted={sessionStarted} onApprove={() => setStep('run')} onEdit={() => setStep('brief')} />}
    {step === 'plan' && !state.diagnosis && !state.approvedPlan && <section className="card"><p className="muted">Медиаплан ещё не рассчитан. Заполните бриф.</p></section>}

    {step === 'run' && state.session && state.activeDraft && state.activePlan && state.approvedPlan && <CampaignStep
      session={state.session} activeDraft={state.activeDraft} activePlan={state.activePlan} approvedPlan={state.approvedPlan} planRevisions={state.planRevisions}
      history={state.history} facts={state.facts} historyCount={state.historyCount} completedRuns={state.completedRuns}
      execution={execution} blocked={blocked} playbackDelayMs={playbackDelayMs}
      onPlaybackDelayChange={(delay) => { playbackDelayRef.current = delay; setPlaybackDelayMs(delay) }}
      onStep={() => void oneHour()} onRun={() => void runToEnd()} onStop={() => { stopRef.current = true; setExecution('stopping') }}
      onNewCampaign={() => setStep('brief')} />}

    {step === 'world' && <WorldTab metadata={metadata} />}
  </>
}
