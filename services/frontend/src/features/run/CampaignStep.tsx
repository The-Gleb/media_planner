import { lazy, Suspense, useMemo } from 'react'
import type { ActivePlan, CampaignFacts, CompletedRun } from '../../domain/planning'
import type { ActiveRun, ExecutionMode, ExecutionStatus, HourlyResult, LaunchDraft } from '../../domain/types'
import type { PlanRevision } from '../campaign/campaignState'
import { channelLabel, count, EXECUTION_LABEL, KPI_LABEL, KPI_LABEL_GENITIVE, kpiOfFacts, money, shortHash, signedPercent } from '../../app/format'
import { useViewMode } from '../../app/viewMode'
import { channelColor } from '../../app/palette'
import { RunProgress } from '../execution/RunProgress'
import { StepControls } from '../execution/StepControls'
import { PlanVsFact } from '../results/PlanVsFact'
import { LatestObservations } from '../results/LatestObservations'
import { StrategyComparison } from '../results/StrategyComparison'
import { currentDeviation, hasTrajectory, planTrajectory } from '../results/planTrajectory'
import { CampaignSummary } from '../campaign/CampaignSummary'
import { AllocationTable } from '../planning/AllocationTable'
import { reallocation, remainingByChannel } from '../plan/planAggregates'
import { Pair, Tile } from '../plan/PlanStep'
import { formatMoney, parseMoney } from '../../domain/numeric'

const MetricHistory = lazy(() => import('../results/MetricHistory').then((module) => ({ default: module.MetricHistory })))

interface Props {
  session: ActiveRun
  activeDraft: LaunchDraft
  activePlan: ActivePlan
  approvedPlan: ActivePlan
  planRevisions: PlanRevision[]
  history: HourlyResult[]
  facts: CampaignFacts
  historyCount: number
  completedRuns: CompletedRun[]
  execution: ExecutionStatus
  blocked: boolean
  playbackDelayMs: number
  onPlaybackDelayChange: (delay: number) => void
  onStep: () => void
  onRun: () => void
  onStop: () => void
  onNewCampaign: () => void
}

export function CampaignStep(props: Props) {
  const { session, activeDraft, activePlan, approvedPlan, planRevisions, history, facts, historyCount, completedRuns, execution } = props
  const { expert } = useViewMode()
  const mode: ExecutionMode = activeDraft.campaign.execution
  const kpi = activePlan.optimize
  const finished = session.status === 'finished'
  const points = useMemo(() => hasTrajectory(approvedPlan) ? planTrajectory(approvedPlan, history, kpi) : [], [approvedPlan, history, kpi])
  const deviation = useMemo(() => currentDeviation(points, history.length), [points, history.length])
  const planKpiEnd = points.at(-1)?.planKpi ?? null
  const planSpendEnd = points.at(-1)?.planSpend ?? null
  const factKpi = Number(kpiOfFacts(facts, kpi))
  const running = execution === 'running' || execution === 'stopping'
  const status = running ? 'В эфире' : finished ? 'Завершена' : history.length === 0 ? 'Готова к запуску' : 'Пауза'

  return <div className="stack">
    <section className="card stack control-panel" aria-labelledby="control-title">
      <div className="card-head">
        <div><h2 id="control-title">Ход кампании</h2><p className="muted">Один шаг — один час кампании. Трафик-менеджер видит факт по каналам и то, как остаток бюджета перекладывается между ними.</p></div>
        <div className="chips"><span className="chip">{EXECUTION_LABEL[mode]}</span><span className="chip" data-tone={running ? 'ok' : finished ? 'good' : undefined}>{status}</span></div>
      </div>
      {activeDraft.campaign.planType === 'target_kpi' && <p className="note">{session.completionReason === 'kpi_reached'
        ? `Целевой KPI достигнут. Кампания завершена, остаток бюджета ${money(formatMoney(parseMoney(activePlan.budget) - parseMoney(facts.spent)), session.currency)} сохранён.`
        : session.completionReason === 'budget_spent' ? 'Расчётный бюджет израсходован. Кампания завершена.'
        : activeDraft.campaign.kpiCompletionPolicy === 'stop_at_kpi' ? 'При достижении целевого KPI кампания завершится после текущего часа.' : 'После достижения KPI продолжаем расходовать расчётный бюджет на дополнительный результат.'}</p>}
      {activeDraft.campaign.audience && <p className="note">Показы ограничены выбранной в брифе аудиторией в {Object.keys(activeDraft.campaign.audience).length} каналах. Выбор зафиксирован на весь прогон; первоначальный прогноз относится к каналам в целом.</p>}
      <RunProgress session={session} status={execution} />
      <StepControls session={session} status={execution} blocked={props.blocked} playbackDelayMs={props.playbackDelayMs} onPlaybackDelayChange={props.onPlaybackDelayChange} onStep={props.onStep} onRun={props.onRun} onStop={props.onStop} />
    </section>

    <section className="card stack" aria-labelledby="scoreboard-title">
      <div className="card-head"><div><h2 id="scoreboard-title">{finished ? 'Итог кампании' : 'Факт против плана'}</h2><p className="muted">{deviation ? `После ${deviation.hour} из ${points.length} часов. Допустимое отклонение по кейсу — 20 %.` : 'Кампания ещё не стартовала: ниже утверждённый план на конец срока.'}</p></div></div>
      <div className="kpi-grid kpi-grid-5">
        <Tile label="Потрачено" value={money(facts.spent, session.currency)} hint={planSpendEnd === null ? undefined : `план на конец ${money(planSpendEnd, session.currency)}`} />
        <Tile label="Отклонение расхода" value={signedPercent(deviation?.spend)} hint="от накопленного плана" tone={toneOf(deviation?.spend)} />
        <Tile label={KPI_LABEL[kpi]} value={count(factKpi)} hint={planKpiEnd === null ? undefined : `план на конец ${count(Math.round(planKpiEnd))}`} tone="accent" />
        <Tile label={`Отклонение ${KPI_LABEL_GENITIVE[kpi]}`} value={signedPercent(deviation?.kpi)} hint="от накопленного плана" tone={toneOf(deviation?.kpi)} />
        <Tile label={kpi === 'unique_reach' ? 'CPM охвата' : kpi === 'clicks' ? 'CPC факт' : 'CPA факт'} value={factKpi > 0 ? money(Number(facts.spent) / factKpi * (kpi === 'unique_reach' ? 1000 : 1), session.currency, kpi === 'clicks' ? 1 : 0) : '—'} hint={`${count(facts.clicks)} кликов · ${count(facts.conversions)} конверсий`} />
      </div>
    </section>

    {completedRuns.length > 0 && <StrategyComparison previous={completedRuns.at(-1)!} current={{ audience: session.audience, strategy: activeDraft.campaign.strategy, optimize: activeDraft.campaign.optimize, facts, finished, execution: mode, historyCount, planSpend: approvedPlan.expected?.spend ?? null, planKpi: approvedPlan.expected?.[kpi === 'unique_reach' ? 'uniqueReach' : kpi] ?? null }} />}

    <PlanVsFact approved={approvedPlan} history={history} channelIds={session.channelIds} currency={session.currency} execution={mode} running={running} />

    <ReallocationPanel approved={approvedPlan} current={activePlan} revisions={planRevisions} facts={facts} channelIds={session.channelIds} currency={session.currency} mode={mode} expert={expert} />

    {history.length > 0 && <Suspense fallback={<section className="card" aria-busy="true">Подготовка графика…</section>}>
      <MetricHistory history={history} channelIds={session.channelIds} currency={session.currency} timeZone={session.timeZone} running={running} showInspector={expert} />
    </Suspense>}

    {expert && history.length > 0 && <LatestObservations result={history.at(-1)!} currency={session.currency} />}
    {expert && <>
      <AllocationTable plan={activePlan} currentHour={facts.currentHour} />
      <CampaignSummary session={session} activeDraft={activeDraft} />
    </>}

    <div className="actions actions-end">
      <button type="button" className="secondary" onClick={props.onNewCampaign}>{finished ? 'Новая кампания или сравнение стратегий' : 'Изменить бриф'}</button>
    </div>
  </div>
}

function toneOf(value: number | null | undefined): 'good' | 'bad' | undefined {
  if (value === null || value === undefined) return undefined
  return Math.abs(value) <= 0.2 ? 'good' : 'bad'
}

function ReallocationPanel({ approved, current, revisions, facts, channelIds, currency, mode, expert }: {
  approved: ActivePlan; current: ActivePlan; revisions: PlanRevision[]; facts: CampaignFacts; channelIds: string[]; currency: string; mode: ExecutionMode; expert: boolean
}) {
  const sorted = useMemo(() => [...channelIds].sort(), [channelIds])
  const currentHour = facts.currentHour
  const approvedTotals = useMemo(() => remainingByChannel(approved, approved.horizon.fromHour), [approved])
  /** Fact spent so far plus what the current plan still intends to spend. */
  const currentTotals = useMemo(() => {
    const remainingCurrent = remainingByChannel(current, currentHour)
    const result = new Map<string, bigint>()
    for (const id of sorted) result.set(id, parseMoney(facts.channels[id]?.spent ?? '0') + (remainingCurrent.get(id) ?? 0n))
    return result
  }, [current, currentHour, facts, sorted])
  const journal = useMemo(() => revisions.slice(1).map((entry, index) => reallocation(revisions[index].plan, entry.plan, entry.hour, entry.revision)).filter((item) => item.shifts.some((shift) => shift.deltaMicros !== 0n)), [revisions])
  const maxBudget = Math.max(1, ...sorted.map((id) => Math.max(Number(formatMoney(approvedTotals.get(id) ?? 0n)), Number(formatMoney(currentTotals.get(id) ?? 0n)))))
  const shown = expert ? journal : journal.slice(-8)
  const max2 = (id: string) => { const a = approvedTotals.get(id) ?? 0n, b = currentTotals.get(id) ?? 0n; return a > b ? a : b }

  return <section className="card stack" aria-labelledby="realloc-title">
    <div className="card-head">
      <div><h2 id="realloc-title">Как перераспределялись средства</h2><p className="muted">{mode === 'frozen' ? 'План заморожен: лимиты исполняются как утверждены, перераспределений нет. Это базовая линия для сравнения.' : `Планировщик пересчитывает остаток бюджета после каждого часа. Здесь — утверждённые лимиты по каналам против текущего плана и журнал переносов.`}</p></div>
      <div className="chips"><span className="chip chip-muted">ревизий плана: {revisions.length}</span><span className="chip chip-muted">переносов: {journal.length}</span></div>
    </div>
    <div className="table-region" role="region" aria-label="Утверждённый и текущий бюджет по каналам" tabIndex={0}>
      <table className="realloc-table">
        <thead><tr><th scope="col">Канал</th><th scope="col">Утверждено</th><th scope="col">Факт + текущий план</th><th scope="col">Изменение</th><th scope="col" className="bar-col"><span className="sr-only">Сравнение</span></th></tr></thead>
        <tbody>{[...sorted].sort((a, b) => Number(max2(b)) - Number(max2(a))).map((id) => {
          const before = approvedTotals.get(id) ?? 0n, after = currentTotals.get(id) ?? 0n, delta = after - before
          const beforeN = Number(formatMoney(before)), afterN = Number(formatMoney(after))
          return <tr key={id} className={before === 0n && after === 0n ? 'row-muted' : undefined}>
            <th scope="row"><span className="swatch" style={{ background: before === 0n && after === 0n ? '#d4d4d8' : channelColor(id, channelIds) }} />{channelLabel(id)}</th>
            <td>{money(formatMoney(before), currency)}</td><td>{money(formatMoney(after), currency)}</td>
            <td className={delta > 0n ? 'delta-up' : delta < 0n ? 'delta-down' : 'muted'}>{delta === 0n ? '—' : `${delta > 0n ? '+' : '−'}${money(formatMoney(delta < 0n ? -delta : delta), currency)}`}</td>
            <td className="bar-col"><div className="twin-bar" aria-hidden="true"><span className="twin-before" style={{ width: `${beforeN / maxBudget * 100}%` }} /><span className="twin-after" style={{ width: `${afterN / maxBudget * 100}%`, background: channelColor(id, channelIds) }} /></div></td>
          </tr>
        })}</tbody>
      </table>
    </div>
    {journal.length > 0 && <>
      <h3>Журнал переносов {!expert && journal.length > shown.length ? `(последние ${shown.length})` : ''}</h3>
      <ol className={'journal' + (expert ? ' journal-scroll' : '')}>{shown.map((item) => {
        const gains = item.shifts.filter((s) => s.deltaMicros > 0n).slice(0, 3), losses = item.shifts.filter((s) => s.deltaMicros < 0n).slice(0, 3)
        return <li key={item.revision}><span className="journal-hour">день {Math.floor(item.hour / 24) + 1} · час {item.hour}</span><span className="journal-body">перенесено {money(item.moved, currency)}: {losses.map((s) => `${channelLabel(s.channelId)} −${money(formatMoney(-s.deltaMicros), currency)}`).join(', ')} → {gains.map((s) => `${channelLabel(s.channelId)} +${money(formatMoney(s.deltaMicros), currency)}`).join(', ')}{expert && <span className="muted"> · ревизия {item.revision}</span>}</span></li>
      })}</ol>
    </>}
    {expert && <dl className="pairs"><Pair label="Утверждённый план" value={shortHash(approved.planId, 16)} /><Pair label="Текущий план" value={shortHash(current.planId, 16)} /><Pair label="Правило" value={mode === 'adaptive' ? 'перекладывать, только когда прогноз остатка расходится с утверждённой траекторией; калибровка по окну 72 ч с усадкой к каталогу; детектор скачка' : mode === 'adaptive_max' ? 'каждый час water-filling остатка по откалиброванным по факту параметрам каналов' : 'нет перепланирования'} /></dl>}
  </section>
}
