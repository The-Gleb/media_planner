import type { ActivePlan, KPI, MediaPlan } from '../../domain/planning'
import { formatMoney, parseMoney } from '../../domain/numeric'

export interface ChannelPlanRow {
  channelId: string
  budget: number
  share: number
  impressions: number
  uniqueReach: number
  clicks: number
  conversions: number
  ctr: number | null
  cr: number | null
  cpm: number | null
  cpc: number | null
  cpa: number | null
}

export interface DayPlanRow { day: number; total: number; channels: Record<string, number> }

function ratio(numerator: number, denominator: number): number | null { return denominator > 0 ? numerator / denominator : null }

/** Budget, forecast volumes and unit costs per channel over the whole horizon. */
export function channelRows(plan: MediaPlan): ChannelPlanRow[] {
  const byChannel = new Map<string, ChannelPlanRow>()
  for (const allocation of plan.allocations) {
    let row = byChannel.get(allocation.channelId)
    if (!row) {
      row = { channelId: allocation.channelId, budget: 0, share: 0, impressions: 0, uniqueReach: 0, clicks: 0, conversions: 0, ctr: null, cr: null, cpm: null, cpc: null, cpa: null }
      byChannel.set(allocation.channelId, row)
    }
    row.budget += Number(allocation.budgetCap)
    if (allocation.expected) {
      row.impressions += Number(allocation.expected.impressions)
      row.uniqueReach += Number(allocation.expected.uniqueReach)
      row.clicks += Number(allocation.expected.clicks)
      row.conversions += Number(allocation.expected.conversions)
    }
  }
  const total = Number(plan.budget)
  const rows = [...byChannel.values()].map((row) => ({
    ...row,
    share: total > 0 ? row.budget / total : 0,
    ctr: ratio(row.clicks, row.impressions),
    cr: ratio(row.conversions, row.clicks),
    cpm: row.impressions > 0 ? row.budget / row.impressions * 1000 : null,
    cpc: ratio(row.budget, row.clicks),
    cpa: ratio(row.budget, row.conversions),
  }))
  return rows.sort((a, b) => b.budget - a.budget || a.channelId.localeCompare(b.channelId))
}

/** Spend calendar: planned budget per campaign day and channel. */
export function dayRows(plan: MediaPlan): DayPlanRow[] {
  const days = new Map<number, DayPlanRow>()
  for (const allocation of plan.allocations) {
    const day = Math.floor((allocation.hour - plan.horizon.fromHour) / 24) + 1
    let row = days.get(day)
    if (!row) { row = { day, total: 0, channels: {} }; days.set(day, row) }
    const value = Number(allocation.budgetCap)
    row.total += value
    row.channels[allocation.channelId] = (row.channels[allocation.channelId] ?? 0) + value
  }
  return [...days.values()].sort((a, b) => a.day - b.day)
}

export interface PlanTotals { spend: number; impressions: number; uniqueReach: number; clicks: number; conversions: number; kpi: number; unitCost: number | null; ctr: number | null; cr: number | null; cpm: number | null }

export function planTotals(plan: MediaPlan, kpi: KPI): PlanTotals {
  const expected = plan.expected
  const spend = expected ? Number(expected.spend) : Number(plan.budget) - Number(plan.unallocatedBudget)
  const impressions = expected ? Number(expected.impressions) : 0
  const uniqueReach = expected ? Number(expected.uniqueReach) : 0
  const clicks = expected ? Number(expected.clicks) : 0
  const conversions = expected ? Number(expected.conversions) : 0
  const kpiValue = kpi === 'unique_reach' ? uniqueReach : kpi === 'clicks' ? clicks : conversions
  const unitCost = kpi === 'unique_reach' ? (uniqueReach > 0 ? spend / uniqueReach * 1000 : null) : ratio(spend, kpiValue)
  return { spend, impressions, uniqueReach, clicks, conversions, kpi: kpiValue, unitCost, ctr: ratio(clicks, impressions), cr: ratio(conversions, clicks), cpm: impressions > 0 ? spend / impressions * 1000 : null }
}

export interface ChannelShift { channelId: string; before: string; after: string; deltaMicros: bigint }
export interface Reallocation { hour: number; revision: number; moved: string; shifts: ChannelShift[] }

/** Remaining budget per channel from `fromHour` onwards. */
export function remainingByChannel(plan: ActivePlan, fromHour: number): Map<string, bigint> {
  const totals = new Map<string, bigint>()
  for (const allocation of plan.allocations) {
    if (allocation.hour < fromHour) continue
    totals.set(allocation.channelId, (totals.get(allocation.channelId) ?? 0n) + parseMoney(allocation.budgetCap))
  }
  return totals
}

/** How a replanning round moved the remaining budget between channels. */
export function reallocation(previous: ActivePlan, next: ActivePlan, hour: number, revision: number): Reallocation {
  const before = remainingByChannel(previous, hour)
  const after = remainingByChannel(next, hour)
  const channels = [...new Set([...before.keys(), ...after.keys()])].sort()
  const shifts: ChannelShift[] = channels.map((channelId) => {
    const a = before.get(channelId) ?? 0n, b = after.get(channelId) ?? 0n
    return { channelId, before: formatMoney(a), after: formatMoney(b), deltaMicros: b - a }
  })
  const moved = shifts.reduce((sum, shift) => shift.deltaMicros > 0n ? sum + shift.deltaMicros : sum, 0n)
  return { hour, revision, moved: formatMoney(moved), shifts: shifts.sort((x, y) => (y.deltaMicros > x.deltaMicros ? 1 : y.deltaMicros < x.deltaMicros ? -1 : 0)) }
}
