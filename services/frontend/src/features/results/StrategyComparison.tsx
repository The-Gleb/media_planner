import { audienceEqual, type Audience } from '../../domain/audience'
import type { CampaignFacts, CompletedRun, KPI, Strategy } from '../../domain/planning'

import type { ExecutionMode } from '../../domain/types'

const strategyLabel: Record<Strategy, string> = { uniform: 'Равномерная', optimized: 'Оптимизированная' }
const executionLabel: Record<ExecutionMode, string> = { adaptive_max: 'максимизация KPI', adaptive: 'удержание плана', frozen: 'заморожен' }
function deviation(fact: string, plan: string | null | undefined): string { if (!plan || Number(plan) <= 0) return '—'; const value = Number(fact) / Number(plan) - 1; return `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)} %` }
function kpiFact(facts: CampaignFacts, optimize: KPI): string { return optimize === 'unique_reach' ? facts.uniqueReach : facts[optimize] }
const kpiLabel: Record<KPI, string> = { unique_reach: 'Охват', clicks: 'Клики', conversions: 'Конверсии' }

type CurrentRun = { audience?: Audience; strategy: Strategy; optimize: KPI; facts: CampaignFacts; finished: boolean; execution?: ExecutionMode; historyCount?: number; planSpend?: string | null; planKpi?: string | null }
export function StrategyComparison({ previous, current }: { previous: CompletedRun; current: CurrentRun }) {
  if (!audienceEqual(previous.audience, current.audience)) return <section className="card"><p>Аудитории запусков различаются; прямое сравнение стратегий некорректно.</p></section>
  return <section className="card" aria-labelledby="comparison-title"><div className="status-line"><h2 id="comparison-title">Сравнение стратегий</h2><span className="status-badge" data-tone={current.finished ? 'ok' : undefined}>{current.finished ? 'Два прогона завершены' : 'Второй прогон выполняется'}</span></div>
    <p className="muted">Одинаковые simulation ID и seed, последовательные запуски после reset. Отклонение считается от утверждённого плана каждого прогона; порог кейса — 20 %.</p>
    <div className="table-region" tabIndex={0}><table><thead><tr><th>Стратегия</th><th>Исполнение</th><th>История</th><th>Целевой KPI</th><th>Расход</th><th>Охват*</th><th>Клики</th><th>Конверсии</th><th>Откл. расхода от плана</th><th>Откл. KPI от плана</th></tr></thead><tbody>
      <Row run={previous} />
      <Row run={current} />
    </tbody></table></div><p className="muted">* Охват суммируется по каналам без межканальной дедупликации.</p>
  </section>
}

function Row({ run }: { run: CurrentRun | CompletedRun }) {
  const { strategy, optimize, facts } = run
  return <tr><th>{strategyLabel[strategy]}</th><td>{run.execution ? executionLabel[run.execution] : '—'}</td><td>{run.historyCount ? `${run.historyCount} камп.` : 'каталог'}</td><td>{kpiLabel[optimize]}</td><td>{facts.spent}</td><td>{facts.uniqueReach}</td><td>{facts.clicks}</td><td>{facts.conversions}</td><td>{deviation(facts.spent, run.planSpend)}</td><td>{deviation(kpiFact(facts, optimize), run.planKpi)}</td></tr>
}
