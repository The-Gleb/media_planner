import type { HourlyResult, MetricKey, Observation } from '../../domain/types'
import { toChartNumber } from '../../domain/numeric'

const COLORS = ['#0d6b58', '#bc5a26', '#315ca8', '#8b4aa0', '#927000', '#327a8a', '#c33f62', '#59636d']
const DASHES = ['', '8 4', '3 3', '12 4 3 4']

export interface SeriesDefinition { id: string; label: string; color: string; dash: string; aggregate: boolean }
export type ChartRow = { hour: string } & Record<string, string | number | null>

export function seriesDefinitions(channelIds: readonly string[], metric: MetricKey): SeriesDefinition[] {
  const channels = channelIds.map((id, index) => ({ id, label: id, color: COLORS[index % COLORS.length], dash: DASHES[Math.floor(index / COLORS.length) % DASHES.length], aggregate: false }))
  return [...channels, { id: 'aggregate', label: metric === 'unique_reach' ? 'Итого (без дедупликации)' : 'Итого', color: '#111827', dash: '10 4', aggregate: true }]
}

function observationValue(observation: Observation, metric: MetricKey): bigint | string | null {
  if (metric === 'unique_reach') return observation.uniqueReach
  return observation[metric]
}

export function exactMetricValue(result: HourlyResult, seriesId: string, metric: MetricKey): string | null {
  const source = seriesId === 'aggregate' ? result.aggregate : result.observations.find((item) => item.channelId === seriesId)
  if (!source) return null
  const value = metric === 'unique_reach' ? source.uniqueReach : source[metric]
  return value === null ? null : value.toString()
}

export function chartRows(history: readonly HourlyResult[], channelIds: readonly string[], metric: MetricKey): ChartRow[] {
  return history.map((result) => {
    const row: ChartRow = { hour: result.observedHour }
    for (const channelId of channelIds) {
      const observation = result.observations.find((item) => item.channelId === channelId)
      row[channelId] = observation ? toChartNumber(observationValue(observation, metric)) : null
    }
    const exact = exactMetricValue(result, 'aggregate', metric)
    row.aggregate = exact === null ? null : Number(exact)
    return row
  })
}
