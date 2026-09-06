import type { ActivePlan, KPI } from '../../domain/planning'
import type { HourlyResult } from '../../domain/types'
import { parseMoney } from '../../domain/numeric'

export interface TrajectoryPoint { hour: number; planSpend: number; factSpend: number | null; planKpi: number; factKpi: number | null }
export interface Deviation { hour: number; spend: number | null; kpi: number | null }

function kpiOf(source: { uniqueReach: bigint; clicks: bigint; conversions: bigint }, kpi: KPI): bigint {
  return kpi === 'unique_reach' ? source.uniqueReach : source[kpi]
}

/** Cumulative approved plan against cumulative fact, one point per campaign hour. */
export function planTrajectory(approved: ActivePlan, history: readonly HourlyResult[], kpi: KPI): TrajectoryPoint[] {
  const hours = approved.horizon.toHour - approved.horizon.fromHour
  const planSpendByHour = new Array<number>(hours).fill(0)
  const planKpiByHour = new Array<number>(hours).fill(0)
  for (const allocation of approved.allocations) {
    const index = allocation.hour - approved.horizon.fromHour
    if (!allocation.expected || index < 0 || index >= hours) continue
    planSpendByHour[index] += Number(allocation.expected.spend)
    planKpiByHour[index] += Number(allocation.expected[kpi === 'unique_reach' ? 'uniqueReach' : kpi])
  }
  const points: TrajectoryPoint[] = []
  let planSpend = 0, planKpi = 0, factSpendMicros = 0n, factKpi = 0n
  for (let hour = 0; hour < hours; hour++) {
    planSpend += planSpendByHour[hour]
    planKpi += planKpiByHour[hour]
    const result = history[hour]
    if (result?.aggregate) { factSpendMicros += parseMoney(result.aggregate.spend); factKpi += kpiOf(result.aggregate, kpi) }
    points.push({ hour: hour + 1, planSpend, planKpi, factSpend: result ? Number(factSpendMicros) / 1e6 : null, factKpi: result ? Number(factKpi) : null })
  }
  return points
}

/** Signed deviation of the cumulative fact from the cumulative plan at the latest committed hour. */
export function currentDeviation(points: readonly TrajectoryPoint[], committedHours: number): Deviation | null {
  if (committedHours <= 0) return null
  const point = points[Math.min(committedHours, points.length) - 1]
  if (!point || point.factSpend === null || point.factKpi === null) return null
  return {
    hour: point.hour,
    spend: point.planSpend > 0 ? point.factSpend / point.planSpend - 1 : null,
    kpi: point.planKpi > 0 ? point.factKpi / point.planKpi - 1 : null,
  }
}

export function hasTrajectory(approved: ActivePlan): boolean {
  return approved.allocations.some((allocation) => allocation.expected !== null)
}
