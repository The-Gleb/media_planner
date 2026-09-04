import type { HourlyAggregate, Observation } from './types'
import { aggregateECPMMicros, formatMoney, parseMoney } from './numeric'

export function aggregateObservations(observations: readonly Observation[]): HourlyAggregate {
  let requests = 0n, impressions = 0n, uniqueReach = 0n, clicks = 0n, conversions = 0n, spendMicros = 0n
  for (const observation of observations) {
    requests += observation.requests
    impressions += observation.impressions
    uniqueReach += observation.uniqueReach
    clicks += observation.clicks
    conversions += observation.conversions
    spendMicros += parseMoney(observation.spend)
  }
  const ecpmMicros = aggregateECPMMicros(spendMicros, impressions)
  return {
    requests, impressions, uniqueReach, clicks, conversions,
    spend: formatMoney(spendMicros),
    ecpm: ecpmMicros === null ? null : formatMoney(ecpmMicros),
  }
}
