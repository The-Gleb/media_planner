import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { HourlyResult } from '../../domain/types'
import { dailySpendRows, dailySpendTotal, formatSpendDay, spendDays } from './dailySpend'
import { channelColor } from '../../app/palette'
import { channelLabel, money } from '../../app/format'

const LATEST = '__latest__'

export function DailySpendChart({ history, channelIds, currency, timeZone, running }: {
  history: HourlyResult[]
  channelIds: string[]
  currency: string
  timeZone: string
  running: boolean
}) {
  const days = useMemo(() => spendDays(history, timeZone), [history, timeZone])
  const latestDay = days.at(-1) ?? ''
  const [selection, setSelection] = useState(LATEST)
  const selectedDay = selection === LATEST || !days.includes(selection) ? latestDay : selection
  const rows = useMemo(() => dailySpendRows(history, channelIds, timeZone, selectedDay), [history, channelIds, timeZone, selectedDay])
  const total = useMemo(() => dailySpendTotal(history, timeZone, selectedDay), [history, timeZone, selectedDay])

  return <section className="card" aria-labelledby="daily-spend-title">
    <div className="status-line">
      <h2 id="daily-spend-title">Дневной расход по часам</h2>
      {running && selection === LATEST && <span className="live-indicator"><span aria-hidden="true" />Текущий день</span>}
    </div>
    <div className="daily-spend-toolbar">
      <div className="field">
        <label htmlFor="spend-day">День кампании</label>
        <select id="spend-day" value={selection} onChange={(event) => setSelection(event.target.value)}>
          <option value={LATEST}>Текущий · {formatSpendDay(latestDay)}</option>
          {days.slice(0, -1).reverse().map((day) => <option key={day} value={day}>{formatSpendDay(day)}</option>)}
        </select>
      </div>
      <div className="daily-spend-total"><span>Расход за выбранный день</span><strong>{money(total, currency)}</strong><small>{timeZone}</small></div>
    </div>
    <p className="muted">Столбец показывает общий расход за час, цветные сегменты — вклад каждого канала.</p>
    <div className="chart-wrap daily-spend-chart" role="img" aria-label={`Почасовое распределение расходов по каналам за ${formatSpendDay(selectedDay)}. Валюта: ${currency}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} accessibilityLayer margin={{ top: 12, right: 20, bottom: 12, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="hour" interval={2} />
          <YAxis width={82} />
          <Tooltip formatter={(v) => money(String(v), currency, 2)} />
          <Legend />
          {channelIds.map((channelId) => <Bar key={channelId} dataKey={channelId} name={channelLabel(channelId)} stackId="daily-spend" fill={channelColor(channelId, channelIds)} isAnimationActive={!running} />)}
        </BarChart>
      </ResponsiveContainer>
    </div>
  </section>
}
