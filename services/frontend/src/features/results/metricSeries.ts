import type { HourlyResult, MetricKey, Observation } from '../../domain/types'
import { formatMoney, parseMoney, toChartNumber } from '../../domain/numeric'
import { channelColor, TOTAL_STROKE } from '../../app/palette'
import { channelLabel } from '../../app/format'


export interface SeriesDefinition { id: string; label: string; color: string; dash: string; aggregate: boolean }
export type ChartRow = { hour: string } & Record<string, string | number | null>

export function seriesDefinitions(channelIds: readonly string[], metric: MetricKey): SeriesDefinition[] {
  const channels = channelIds.map((id) => ({ id, label: channelLabel(id), color: channelColor(id, channelIds), dash: '', aggregate: false }))
  return [...channels, { id: 'aggregate', label: metric === 'unique_reach' ? 'Итого (без дедупликации)' : 'Итого', color: TOTAL_STROKE, dash: '10 4', aggregate: true }]
}

type MetricSource = Observation | NonNullable<HourlyResult['aggregate']>

function formatPercent(numerator: bigint, denominator: bigint): string | null {
  if (denominator === 0n) return null
  const scaled = (numerator * 1_000_000n + denominator / 2n) / denominator
  return `${scaled / 10_000n}.${(scaled % 10_000n).toString().padStart(4, '0')}`
}

function formatCost(spend: string, denominator: bigint): string | null {
  if (denominator === 0n) return null
  const micros = parseMoney(spend)
  return formatMoney((micros + denominator / 2n) / denominator)
}

function metricValue(source: MetricSource, metric: MetricKey): bigint | string | null {
  switch (metric) {
    case 'unique_reach': return source.uniqueReach
    case 'ctr': return formatPercent(source.clicks, source.impressions)
    case 'cr': return formatPercent(source.conversions, source.clicks)
    case 'cpc': return formatCost(source.spend, source.clicks)
    case 'cpa': return formatCost(source.spend, source.conversions)
    default: return source[metric]
  }
}

export function exactMetricValue(result: HourlyResult, seriesId: string, metric: MetricKey): string | null {
  const source = seriesId === 'aggregate' ? result.aggregate : result.observations.find((item) => item.channelId === seriesId)
  if (!source) return null
  const value = metricValue(source, metric)
  return value === null ? null : value.toString()
}

export function chartRows(history: readonly HourlyResult[], channelIds: readonly string[], metric: MetricKey): ChartRow[] {
  return history.map((result) => {
    const row: ChartRow = { hour: result.observedHour }
    for (const channelId of channelIds) {
      const observation = result.observations.find((item) => item.channelId === channelId)
      row[channelId] = observation ? toChartNumber(metricValue(observation, metric)) : null
    }
    const exact = exactMetricValue(result, 'aggregate', metric)
    row.aggregate = exact === null ? null : Number(exact)
    return row
  })
}

export function metricUnit(metric: MetricKey, currency: string): string {
  if (metric === 'ctr' || metric === 'cr') return '%'
  if (metric === 'spend' || metric === 'ecpm' || metric === 'cpc' || metric === 'cpa') return currency
  return 'шт.'
}
