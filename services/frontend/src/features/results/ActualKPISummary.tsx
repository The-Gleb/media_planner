import type { CampaignFacts } from '../../domain/planning'

export function ActualKPISummary({
  facts,
  currency,
  finished,
}: {
  facts: CampaignFacts
  currency: string
  finished: boolean
}) {
  const impressions = Object.values(facts.channels)
    .reduce((total, channel) => total + BigInt(channel.impressions), 0n)
    .toString()
  const qualifier = finished ? 'Итоговые' : 'Фактически на текущий момент'
  return <section className={'card actual-kpis ' + (finished ? 'final' : '')} aria-labelledby="actual-kpi-title">
    <div className="status-line">
      <h2 id="actual-kpi-title">{finished ? 'Итоговые результаты' : 'Фактические результаты'}</h2>
      <span className="status-badge" data-tone={finished ? 'ok' : undefined}>{finished ? 'Финал' : `После ${facts.currentHour} ч`}</span>
    </div>
    <div className="kpi-grid">
      <KPI label={`Расход, ${currency}`} qualifier={qualifier} value={facts.spent} />
      <KPI label="Показы" qualifier={qualifier} value={impressions} />
      <KPI label="Охват" qualifier={`${finished ? 'Итоговый' : qualifier}; сумма по каналам, без дедупликации`} value={facts.uniqueReach} />
      <KPI label="Клики" qualifier={qualifier} value={facts.clicks} />
      <KPI label="Конверсии" qualifier={qualifier} value={facts.conversions} />
    </div>
  </section>
}

function KPI({ label, qualifier, value }: { label: string; qualifier: string; value: string }) {
  return <article className="kpi-card"><span>{label}</span><strong>{value}</strong><small>{qualifier}</small></article>
}
