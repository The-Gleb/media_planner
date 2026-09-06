import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ActivePlan } from '../../domain/planning'
import type { ExecutionMode, HourlyResult } from '../../domain/types'
import { currentDeviation, hasTrajectory, planTrajectory } from './planTrajectory'

const KPI_LABEL = { unique_reach: 'охват', clicks: 'клики', conversions: 'конверсии' } as const
const EXECUTION_LABEL: Record<ExecutionMode, string> = { adaptive_max: 'Максимизация KPI', adaptive: 'Удержание плана', frozen: 'Замороженный план' }

function percent(value: number | null): string {
  if (value === null) return '—'
  return `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)} %`
}

function tone(value: number | null): 'ok' | 'warn' | undefined {
  if (value === null) return undefined
  return Math.abs(value) <= 0.2 ? 'ok' : 'warn'
}

export function PlanVsFact({ approved, history, currency, execution }: { approved: ActivePlan; history: HourlyResult[]; channelIds: string[]; currency: string; execution: ExecutionMode }) {
  const points = useMemo(() => planTrajectory(approved, history, approved.optimize), [approved, history])
  const deviation = useMemo(() => currentDeviation(points, history.length), [points, history.length])
  if (!hasTrajectory(approved)) return <section className="card" aria-labelledby="plan-fact-title"><h2 id="plan-fact-title">План против факта</h2><p className="forecast-unavailable">Утверждённый план не содержит почасового прогноза: каналы вне публичного каталога.</p></section>
  const kpiLabel = KPI_LABEL[approved.optimize]
  return <section className="card stack" aria-labelledby="plan-fact-title">
    <div className="status-line"><div><p className="eyebrow">УТВЕРЖДЁННЫЙ ПЛАН</p><h2 id="plan-fact-title">План против факта</h2></div><span className="status-badge">{EXECUTION_LABEL[execution]}</span></div>
    <p className="muted">Пунктир — накопительная траектория утверждённого плана (ревизия 0), сплошная — накопленный факт. Отклонение считается на последнем завершённом часе; порог кейса — 20 %.</p>
    <dl className="summary-grid">
      <div className="summary-item"><dt>Часов прошло</dt><dd>{deviation ? deviation.hour : 0} из {points.length}</dd></div>
      <div className="summary-item"><dt>Отклонение расхода</dt><dd><span className="status-badge" data-tone={tone(deviation?.spend ?? null)}>{percent(deviation?.spend ?? null)}</span></dd></div>
      <div className="summary-item"><dt>Отклонение KPI ({kpiLabel})</dt><dd><span className="status-badge" data-tone={tone(deviation?.kpi ?? null)}>{percent(deviation?.kpi ?? null)}</span></dd></div>
      <div className="summary-item"><dt>План на конец</dt><dd>{Math.round(points.at(-1)?.planKpi ?? 0).toLocaleString('ru-RU')} {kpiLabel} · {Math.round(points.at(-1)?.planSpend ?? 0).toLocaleString('ru-RU')} {currency}</dd></div>
    </dl>
    <div className="plan-fact-charts">
      <Trajectory title={`Накопленный расход, ${currency}`} rows={points} planKey="planSpend" factKey="factSpend" />
      <Trajectory title={`Накопленные ${kpiLabel}`} rows={points} planKey="planKpi" factKey="factKpi" />
    </div>
  </section>
}

function Trajectory({ title, rows, planKey, factKey }: { title: string; rows: ReturnType<typeof planTrajectory>; planKey: 'planSpend' | 'planKpi'; factKey: 'factSpend' | 'factKpi' }) {
  return <div className="chart-wrap plan-fact-chart" role="img" aria-label={title}>
    <p className="chart-title">{title}</p>
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="hour" tickFormatter={(v) => `${Math.ceil(Number(v) / 24)} д`} minTickGap={24} />
        <YAxis width={82} tickFormatter={(v) => Number(v).toLocaleString('ru-RU')} />
        <Tooltip labelFormatter={(v) => `час ${v}`} formatter={(v) => (v === null ? '—' : Number(v).toLocaleString('ru-RU', { maximumFractionDigits: 0 }))} />
        <Line type="monotone" dataKey={planKey} name="план" stroke="#315ca8" strokeDasharray="8 4" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line type="monotone" dataKey={factKey} name="факт" stroke="#bc5a26" strokeWidth={3} dot={false} connectNulls={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  </div>
}
