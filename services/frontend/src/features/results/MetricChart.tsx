import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ChartRow, SeriesDefinition } from './metricSeries'

export function MetricChart({ rows, series, visible, title, unit, animate }: { rows: ChartRow[]; series: SeriesDefinition[]; visible: Set<string>; title: string; unit: string; animate: boolean }) {
  return <div className="chart-wrap" role="img" aria-label={`${title}. Единица: ${unit}. Точные значения доступны ниже.`}>
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={rows} accessibilityLayer margin={{ top: 16, right: 20, bottom: 18, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="hour" tickFormatter={(v) => new Date(String(v)).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit' })} minTickGap={28} />
        <YAxis width={82} />
        <Tooltip labelFormatter={(v) => new Date(String(v)).toLocaleString('ru-RU')} />
        {series.filter((item) => visible.has(item.id)).map((item) => <Line key={item.id} type="monotone" dataKey={item.id} name={item.label} stroke={item.color} strokeDasharray={item.dash} strokeWidth={item.aggregate ? 3 : 2} dot={false} connectNulls={false} isAnimationActive={animate} />)}
      </LineChart>
    </ResponsiveContainer>
  </div>
}
