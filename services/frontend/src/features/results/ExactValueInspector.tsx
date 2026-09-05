import { useState } from 'react'
import type { HourlyResult, MetricKey } from '../../domain/types'
import { metricLabels } from '../../app/messages'
import { exactMetricValue, metricUnit } from './metricSeries'

export function ExactValueInspector({ history, channelIds, metric, currency }: { history: HourlyResult[]; channelIds: string[]; metric: MetricKey; currency: string }) {
  const last = history.at(-1)
  if (!last) return null
  return <fieldset><legend><strong>Точное значение</strong></legend><ExactForm key={metric} history={history} channelIds={channelIds} metric={metric} currency={currency} /></fieldset>
}

function ExactForm({ history, channelIds, metric, currency }: { history: HourlyResult[]; channelIds: string[]; metric: MetricKey; currency: string }) {
  const [hour, setHour] = useState(history.at(-1)!.observedHour)
  const [series, setSeries] = useState('aggregate')
  const result = history.find((item) => item.observedHour === hour) ?? history.at(-1)!
  const value = exactMetricValue(result, series, metric)
  const unit = metricUnit(metric, currency)
  return <div className="inspector-grid">
    <div className="field"><label htmlFor="inspect-hour">Час</label><select id="inspect-hour" value={hour} onChange={(event) => setHour(event.target.value)}>{history.map((item) => <option key={item.observedHour}>{item.observedHour}</option>)}</select></div>
    <div className="field"><label htmlFor="inspect-series">Ряд</label><select id="inspect-series" value={series} onChange={(event) => setSeries(event.target.value)}><option value="aggregate">Итого</option>{channelIds.map((id) => <option key={id}>{id}</option>)}</select></div>
    <output aria-live="polite"><strong>{metricLabels[metric]}</strong><br />{value ?? '—'} {value === null ? '' : unit}{metric === 'unique_reach' && series === 'aggregate' ? ' · сумма по каналам, без дедупликации' : ''}</output>
  </div>
}
