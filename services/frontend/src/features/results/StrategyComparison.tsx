import { audienceEqual, type Audience } from '../../domain/audience'
import type { CampaignFacts, CompletedRun, KPI, Strategy } from '../../domain/planning'

const strategyLabel: Record<Strategy, string> = { uniform: 'Равномерная', optimized: 'Оптимизированная' }
const kpiLabel: Record<KPI, string> = { unique_reach: 'Охват', clicks: 'Клики', conversions: 'Конверсии' }

export function StrategyComparison({ previous, current }: { previous: CompletedRun; current: { audience?: Audience; strategy: Strategy; optimize: KPI; facts: CampaignFacts; finished: boolean } }) {
  return <section className="card" aria-labelledby="comparison-title"><div className="status-line"><h2 id="comparison-title">Сравнение стратегий</h2><span className="status-badge" data-tone={current.finished ? 'ok' : undefined}>{current.finished ? 'Два прогона завершены' : 'Второй прогон выполняется'}</span></div>
    <p className="muted">Одинаковые simulation ID и seed, последовательные запуски после reset. Одновременно выполняется только одна кампания.</p>
    {!audienceEqual(previous.audience,current.audience) && <p>Аудитории запусков различаются; разница результатов зависит не только от стратегии.</p>}
    <div className="table-region" tabIndex={0}><table><thead><tr><th>Стратегия</th><th>Целевой KPI</th><th>Расход</th><th>Охват*</th><th>Клики</th><th>Конверсии</th></tr></thead><tbody>
      <Row strategy={previous.strategy} optimize={previous.optimize} facts={previous.facts} />
      <Row strategy={current.strategy} optimize={current.optimize} facts={current.facts} />
    </tbody></table></div><p className="muted">* Охват суммируется по каналам без межканальной дедупликации.</p>
  </section>
}

function Row({ strategy, optimize, facts }: { strategy: Strategy; optimize: KPI; facts: CampaignFacts }) {
  return <tr><th>{strategyLabel[strategy]}</th><td>{kpiLabel[optimize]}</td><td>{facts.spent}</td><td>{facts.uniqueReach}</td><td>{facts.clicks}</td><td>{facts.conversions}</td></tr>
}
