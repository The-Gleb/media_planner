import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ActivePlan } from '../../domain/planning'
import type { ExecutionMode, HourlyResult } from '../../domain/types'
import { hasTrajectory, planTrajectory } from './planTrajectory'
import { cachedFormatter } from './formatCache'
import { useThrottled } from './useThrottled'

const yTick = cachedFormatter((v: unknown) => Number(v).toLocaleString('ru-RU'))
const tooltipValue = (v: unknown) => (v === null ? '—' : Number(v).toLocaleString('ru-RU', { maximumFractionDigits: 0 }))
import { FACT_STROKE, PLAN_STROKE } from '../../app/palette'
import { currencySign, EXECUTION_LABEL as EXEC } from '../../app/format'

const KPI_LABEL = { unique_reach: 'охват', clicks: 'клики', conversions: 'конверсии' } as const
const EXECUTION_LABEL = EXEC

export function PlanVsFact({ approved, history, currency, execution, running = false }: { approved: ActivePlan; history: HourlyResult[]; channelIds: string[]; currency: string; execution: ExecutionMode; running?: boolean }) {
  const rendered = useThrottled(history, running)
  const points = useMemo(() => planTrajectory(approved, rendered, approved.optimize), [approved, rendered])
  if (!hasTrajectory(approved)) return <section className="card" aria-labelledby="plan-fact-title"><h2 id="plan-fact-title">План против факта</h2><p className="forecast-unavailable">Утверждённый план не содержит почасового прогноза: каналы вне публичного каталога.</p></section>
  const kpiLabel = KPI_LABEL[approved.optimize]
  return <section className="card stack" aria-labelledby="plan-fact-title">
    <div className="status-line"><h2 id="plan-fact-title">План против факта</h2><span className="status-badge">{EXECUTION_LABEL[execution]}</span></div>
    <p className="muted">Пунктир — накопительная траектория утверждённого плана, сплошная — накопленный факт. Отклонение считается на последнем завершённом часе; допустимый порог — 20 %.</p>
    <div className="plan-fact-charts">
      <Trajectory title={`Накопленный расход, ${currencySign(currency)}`} rows={points} planKey="planSpend" factKey="factSpend" />
      <Trajectory title={`Накопленные ${kpiLabel}`} rows={points} planKey="planKpi" factKey="factKpi" />
    </div>
  </section>
}

function Trajectory({ title, rows, planKey, factKey }: { title: string; rows: ReturnType<typeof planTrajectory>; planKey: 'planSpend' | 'planKpi'; factKey: 'factSpend' | 'factKpi' }) {
  return <div className="chart-wrap plan-fact-chart" role="img" aria-label={title}>
    <p className="chart-title">{title}</p>
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
        <XAxis dataKey="hour" tickFormatter={(v) => `${Math.ceil(Number(v) / 24)} д`} minTickGap={24} />
        <YAxis width={82} tickFormatter={yTick} />
        <Tooltip labelFormatter={(v) => `час ${v}`} formatter={tooltipValue} />
        <Line type="monotone" dataKey={planKey} name="план" stroke={PLAN_STROKE} strokeDasharray="8 4" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line type="monotone" dataKey={factKey} name="факт" stroke={FACT_STROKE} strokeWidth={2.5} dot={false} connectNulls={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  </div>
}
