import { useThrottled } from './useThrottled'
import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { HourlyResult } from '../../domain/types'
import { campaignSpendRows, campaignSpendTotal, dailySpendRows, dailySpendTotal, formatSpendDay, spendDays } from './dailySpend'
import { channelColor } from '../../app/palette'
import { channelLabel, money } from '../../app/format'

const LATEST = '__latest__'
const ALL_DAYS = '__all_days__'
const ALL_HOURS = '__all_hours__'

export function DailySpendChart({ history, channelIds, currency, timeZone, running }: {
  history: HourlyResult[]
  channelIds: string[]
  currency: string
  timeZone: string
  running: boolean
}) {
  const renderedHistory = useThrottled(history, running)
  const days = useMemo(() => spendDays(renderedHistory, timeZone), [renderedHistory, timeZone])
  const latestDay = days.at(-1) ?? ''
  const [selection, setSelection] = useState(ALL_DAYS)
  const wholeCampaign = selection === ALL_DAYS || selection === ALL_HOURS
  const selectedDay = selection === LATEST || !days.includes(selection) ? latestDay : selection
  const rows = useMemo(
    () => wholeCampaign ? campaignSpendRows(renderedHistory, channelIds, timeZone, selection === ALL_DAYS ? 'day' : 'hour') : dailySpendRows(renderedHistory, channelIds, timeZone, selectedDay),
    [wholeCampaign, renderedHistory, channelIds, timeZone, selection, selectedDay],
  )
  const total = useMemo(() => wholeCampaign ? campaignSpendTotal(renderedHistory) : dailySpendTotal(renderedHistory, timeZone, selectedDay), [wholeCampaign, renderedHistory, timeZone, selectedDay])
  const scopeLabel = selection === ALL_DAYS ? 'вся кампания по дням' : selection === ALL_HOURS ? 'вся кампания по часам' : formatSpendDay(selectedDay)

  return <section className="card" aria-labelledby="daily-spend-title">
    <div className="status-line">
      <h2 id="daily-spend-title">Расход по каналам</h2>
      {running && (selection === LATEST || wholeCampaign) && <span className="live-indicator"><span aria-hidden="true" />Обновляется</span>}
    </div>
    <div className="daily-spend-toolbar">
      <div className="field">
        <label htmlFor="spend-day">Период</label>
        <select id="spend-day" value={selection} onChange={(event) => setSelection(event.target.value)}>
          <option value={ALL_DAYS}>Вся кампания · по дням</option>
          <option value={ALL_HOURS}>Вся кампания · по часам</option>
          <option value={LATEST}>Текущий день · {formatSpendDay(latestDay)}</option>
          {days.slice(0, -1).reverse().map((day) => <option key={day} value={day}>{formatSpendDay(day)}</option>)}
        </select>
      </div>
      <div className="daily-spend-total"><span>Расход за период</span><strong>{money(total, currency)}</strong><small>{timeZone}</small></div>
    </div>
    <p className="muted">Столбец показывает общий расход за {selection === ALL_DAYS ? 'день' : 'час'}, цветные сегменты — вклад каждого канала.</p>
    <div className="chart-wrap daily-spend-chart" role="img" aria-label={`Распределение расходов по каналам: ${scopeLabel}. Валюта: ${currency}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} accessibilityLayer margin={{ top: 12, right: 20, bottom: 12, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="hour" interval={selection === ALL_HOURS ? 23 : selection === ALL_DAYS ? 0 : 2} minTickGap={12} />
          <YAxis width={82} />
          <Tooltip formatter={(v) => money(String(v), currency, 2)} />
          <Legend />
          {channelIds.map((channelId) => <Bar key={channelId} dataKey={channelId} name={channelLabel(channelId)} stackId="daily-spend" fill={channelColor(channelId, channelIds)} isAnimationActive={!running} />)}
        </BarChart>
      </ResponsiveContainer>
    </div>
  </section>
}
