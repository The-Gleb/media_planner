import { useDeferredValue, useMemo, useState } from 'react'
import type { HourlyResult, MetricKey } from '../../domain/types'
import { METRICS } from '../../domain/types'
import { metricLabels } from '../../app/messages'
import { METRIC_SHORT } from '../../app/format'
import { chartRows, metricUnit, seriesDefinitions } from './metricSeries'
import { MetricChart } from './MetricChart'
import { ExactValueInspector } from './ExactValueInspector'
import { DailySpendChart } from './DailySpendChart'

export function MetricHistory({ history, channelIds, currency, timeZone, running, showInspector = true, showDailySpend = true }: { history: HourlyResult[]; channelIds: string[]; currency: string; timeZone: string; running: boolean; showInspector?: boolean; showDailySpend?: boolean }) {
  const [metric, setMetric] = useState<MetricKey>('conversions')
  const deferredHistory = useDeferredValue(history)
  const renderedHistory = running ? deferredHistory : history
  const definitions = useMemo(() => seriesDefinitions(channelIds, metric), [channelIds, metric])
  const [hidden, setHidden] = useState<Set<string>>(() => new Set())
  const rows = useMemo(() => chartRows(renderedHistory, channelIds, metric), [renderedHistory, channelIds, metric])
  const visible = useMemo(() => new Set(definitions.filter((item) => !hidden.has(item.id)).map((item) => item.id)), [definitions, hidden])
  const unit = metricUnit(metric, currency)
  return <><section className="card" aria-labelledby="history-title">
    <div className="status-line"><h2 id="history-title">Почасовые показатели по каналам</h2>{running && <span className="live-indicator"><span aria-hidden="true" />Обновляются каждый час</span>}</div>
    <p className="muted">Что происходило по часам: каждая линия — канал, пунктир — итог по всем каналам. Переключайте метрику и скрывайте ряды в легенде.</p>
    <div className="metric-tabs" role="tablist" aria-label="Метрики">
      {METRICS.map((item) => <button key={item} type="button" role="tab" aria-selected={metric === item} onClick={() => setMetric(item)}>{METRIC_SHORT[item]}</button>)}
    </div>
    <div className="legend-controls" aria-label="Видимые ряды">{definitions.map((item) => <label key={item.id}><input type="checkbox" checked={!hidden.has(item.id)} onChange={() => setHidden((current) => { const next = new Set(current); if (next.has(item.id)) next.delete(item.id); else next.add(item.id); return next })} /><span style={{ color: item.color }}>━</span>{item.label}</label>)}</div>
    <MetricChart rows={rows} series={definitions} visible={visible} title={metricLabels[metric]} unit={unit} animate={!running} />
    {showInspector && <ExactValueInspector history={history} channelIds={channelIds} metric={metric} currency={currency} />}
  </section>{showDailySpend && <DailySpendChart history={history} channelIds={channelIds} currency={currency} timeZone={timeZone} running={running} />}</>
}
