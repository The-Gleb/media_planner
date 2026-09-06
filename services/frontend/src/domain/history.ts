import { audienceKey } from './audience'
import type { AudienceSelection, ChannelID, HourlyResult } from './types'
import type { ActivePlan, CampaignFacts } from './planning'
import { formatMoney, parseMoney } from './numeric'

/** One channel hour as the planner accepts it inside `history` and `current.recent_hours`. */
export interface ChannelHourFacts { spent: string; requests: string; impressions: string; unique_reach: string; clicks: string; conversions: string }
export interface HourBinPayload extends ChannelHourFacts { hour: number; hours: number }
export interface DailyFactsPayload extends ChannelHourFacts { day: number; hours: number; reach_before: string; impressions_before: string }
export interface PastCampaignPayload { horizon_hours: number; channels: Record<ChannelID, { bins: HourBinPayload[]; daily: DailyFactsPayload[] }> }
export interface RecentHourPayload { hour: number; channels: Record<ChannelID, ChannelHourFacts> }
export interface ApprovedPayload { kpi_target: string; channel_budgets: Record<ChannelID, string> }

/** A finished campaign kept for later planning on the same market. */
export interface PastCampaignRecord {
  audience?: AudienceSelection
  worldConfigDigest: string
  worldSeed: string
  campaignSeed: string
  simulationId: string
  planId: string
  finishedAt: string
  durationHours: number
  budget: string
  optimize: string
  facts: CampaignFacts
  payload: PastCampaignPayload
}

const HOURS = 24
const RECENT_HOURS = 72

function localHour(observedHour: string, timeZone: string): number {
  const text = new Intl.DateTimeFormat('en-GB', { timeZone, hour: '2-digit', hourCycle: 'h23' }).format(new Date(observedHour))
  return Number(text.slice(0, 2)) % HOURS
}

function zeroBin(hour: number): HourBinPayload {
  return { hour, hours: 0, spent: '0.000000', requests: '0', impressions: '0', unique_reach: '0', clicks: '0', conversions: '0' }
}

function add(target: ChannelHourFacts, spendMicros: bigint, o: { requests: bigint; impressions: bigint; uniqueReach: bigint; clicks: bigint; conversions: bigint }) {
  target.spent = formatMoney(parseMoney(target.spent) + spendMicros)
  target.requests = (BigInt(target.requests) + o.requests).toString()
  target.impressions = (BigInt(target.impressions) + o.impressions).toString()
  target.unique_reach = (BigInt(target.unique_reach) + o.uniqueReach).toString()
  target.clicks = (BigInt(target.clicks) + o.clicks).toString()
  target.conversions = (BigInt(target.conversions) + o.conversions).toString()
}

/** Hour-of-day bins and daily saturation rows per channel from the committed hours of one campaign. */
export function buildPastCampaignPayload(history: readonly HourlyResult[], channelIds: readonly ChannelID[], timeZone: string, durationHours: number): PastCampaignPayload {
  const channels: PastCampaignPayload['channels'] = {}
  for (const channelId of channelIds) {
    const bins = Array.from({ length: HOURS }, (_, hour) => zeroBin(hour))
    const daily: DailyFactsPayload[] = []
    let reach = 0n, impressions = 0n
    history.forEach((result, index) => {
      const observation = result.observations.find((item) => item.channelId === channelId)
      if (!observation) return
      const spendMicros = parseMoney(observation.spend)
      const bin = bins[localHour(result.observedHour, timeZone)]
      bin.hours += 1
      add(bin, spendMicros, observation)
      const day = Math.floor(index / HOURS)
      if (daily.length <= day) daily.push({ day, hours: 0, spent: '0.000000', requests: '0', impressions: '0', unique_reach: '0', clicks: '0', conversions: '0', reach_before: reach.toString(), impressions_before: impressions.toString() })
      const row = daily[day]
      row.hours += 1
      add(row, spendMicros, observation)
      reach += observation.uniqueReach
      impressions += observation.impressions
    })
    channels[channelId] = { bins, daily }
  }
  return { horizon_hours: durationHours, channels }
}

/** The latest committed hours per channel, oldest first, for the planner's windowed calibration. */
export function buildRecentHours(history: readonly HourlyResult[], channelIds: readonly ChannelID[]): RecentHourPayload[] {
  const start = Math.max(0, history.length - RECENT_HOURS)
  return history.slice(start).map((result, offset) => ({
    hour: start + offset,
    channels: Object.fromEntries(channelIds.flatMap((channelId) => {
      const observation = result.observations.find((item) => item.channelId === channelId)
      if (!observation) return []
      return [[channelId, {
        spent: observation.spend, requests: observation.requests.toString(), impressions: observation.impressions.toString(),
        unique_reach: observation.uniqueReach.toString(), clicks: observation.clicks.toString(), conversions: observation.conversions.toString(),
      }]]
    })),
  }))
}

/** The approved plan as a tracking target: its expected KPI and channel budgets. */
export function buildApprovedPayload(plan: ActivePlan): ApprovedPayload | null {
  if (!plan.expected) return null
  const kpi = plan.expected[plan.optimize === 'unique_reach' ? 'uniqueReach' : plan.optimize]
  if (!/^[1-9][0-9]*$/.test(kpi)) return null
  const budgets = new Map<ChannelID, bigint>()
  for (const allocation of plan.allocations) budgets.set(allocation.channelId, (budgets.get(allocation.channelId) ?? 0n) + parseMoney(allocation.budgetCap))
  return { kpi_target: kpi, channel_budgets: Object.fromEntries([...budgets].map(([channelId, micros]) => [channelId, formatMoney(micros)])) }
}

export function sameMarket(record: PastCampaignRecord, worldConfigDigest: string, worldSeed: string, audience?: AudienceSelection): boolean {
  return record.worldConfigDigest === worldConfigDigest && record.worldSeed === worldSeed && audienceKey(record.audience) === audienceKey(audience)
}

const STORAGE_KEY = 'media-planner.past-campaigns'
const MAX_STORED = 12

export function loadPastCampaigns(): PastCampaignRecord[] {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as PastCampaignRecord[]) : []
  } catch { return [] }
}

export function savePastCampaigns(records: readonly PastCampaignRecord[]): void {
  try { globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(records.slice(-MAX_STORED))) } catch { /* storage unavailable */ }
}
