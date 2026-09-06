import type { HourlyResult } from '../../domain/types'
import { formatMoney, parseMoney } from '../../domain/numeric'

export type DailySpendRow = { hour: string } & Record<string, string | number>

const localCache = new Map<string, { date: string; hour: number }>()
function localDateAndHour(iso: string, timeZone: string): { date: string; hour: number } {
  const key = timeZone + '|' + iso
  const hit = localCache.get(key)
  if (hit) return hit
  const computed = computeLocalDateAndHour(iso, timeZone)
  if (localCache.size > 8192) localCache.clear()
  localCache.set(key, computed)
  return computed
}

function computeLocalDateAndHour(iso: string, timeZone: string): { date: string; hour: number } {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(iso))
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? ''
  return { date: `${value('year')}-${value('month')}-${value('day')}`, hour: Number(value('hour')) }
}

export function spendDays(history: readonly HourlyResult[], timeZone: string): string[] {
  return [...new Set(history.map((result) => localDateAndHour(result.observedHour, timeZone).date))]
}

export function dailySpendRows(history: readonly HourlyResult[], channelIds: readonly string[], timeZone: string, day: string): DailySpendRow[] {
  const rows: DailySpendRow[] = Array.from({ length: 24 }, (_, hour): DailySpendRow => ({
    hour: `${hour.toString().padStart(2, '0')}:00`,
    ...Object.fromEntries(channelIds.map((channelId) => [channelId, 0])),
  }))
  const knownChannels = new Set(channelIds)
  for (const result of history) {
    const local = localDateAndHour(result.observedHour, timeZone)
    if (local.date !== day) continue
    for (const observation of result.observations) {
      if (!knownChannels.has(observation.channelId)) continue
      rows[local.hour][observation.channelId] = Number(rows[local.hour][observation.channelId]) + Number(observation.spend)
    }
  }
  return rows
}

export function dailySpendTotal(history: readonly HourlyResult[], timeZone: string, day: string): string {
  let total = 0n
  for (const result of history) {
    if (localDateAndHour(result.observedHour, timeZone).date !== day) continue
    for (const observation of result.observations) total += parseMoney(observation.spend)
  }
  return formatMoney(total)
}

export function formatSpendDay(day: string): string {
  const [year, month, date] = day.split('-').map(Number)
  return new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC', day: 'numeric', month: 'long', year: 'numeric' })
    .format(new Date(Date.UTC(year, month - 1, date, 12)))
}

export type SpendGranularity = 'day' | 'hour'

/** Stacked spend per channel over the whole campaign: one bar per local day or per campaign hour. */
export function campaignSpendRows(history: readonly HourlyResult[], channelIds: readonly string[], timeZone: string, granularity: SpendGranularity): DailySpendRow[] {
  const knownChannels = new Set(channelIds)
  const rows: DailySpendRow[] = []
  const byKey = new Map<string, DailySpendRow>()
  history.forEach((result, index) => {
    const local = localDateAndHour(result.observedHour, timeZone)
    const key = granularity === 'day' ? local.date : `${index}`
    let row = byKey.get(key)
    if (!row) {
      const [, month, date] = local.date.split('-')
      row = { hour: granularity === 'day' ? `${date}.${month}` : `д${Math.floor(index / 24) + 1} ${local.hour.toString().padStart(2, '0')}:00`, ...Object.fromEntries(channelIds.map((channelId) => [channelId, 0])) }
      byKey.set(key, row)
      rows.push(row)
    }
    for (const observation of result.observations) {
      if (!knownChannels.has(observation.channelId)) continue
      row[observation.channelId] = Number(row[observation.channelId]) + Number(observation.spend)
    }
  })
  return rows
}

export function campaignSpendTotal(history: readonly HourlyResult[]): string {
  let total = 0n
  for (const result of history) for (const observation of result.observations) total += parseMoney(observation.spend)
  return formatMoney(total)
}

