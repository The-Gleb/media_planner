export type ChannelID = string
export type MoneyText = string
export type SimulationStatus = 'active' | 'finished'

export const METRICS = [
  'requests',
  'impressions',
  'unique_reach',
  'clicks',
  'conversions',
  'spend',
  'ecpm',
  'ctr',
  'cr',
  'cpc',
  'cpa',
] as const
export type MetricKey = (typeof METRICS)[number]

export interface WorldMetadata {
  engineVersion: string
  worldConfigDigest: string
  currency: string
  channelIds: ChannelID[]
}

export interface AudienceFilters { age: string; gender: string; geo: string }

export type AudienceSelection = Record<ChannelID, { segment_ids: string[] }>

export interface SimulationDraft {
  audience?: AudienceSelection
  audienceFilters?: AudienceFilters
  simulationId: string
  worldSeed: string
  campaignSeed: string
  startHour: string
  timeZone: string
  disableRandomEvents: boolean
  scenario: ScenarioDraft
}

export interface ScenarioDraft {
  enabled: boolean
  channelId: ChannelID
  metric: 'supply' | 'cpm' | 'ctr' | 'cr' | 'pause'
  startIndex: string
  durationHours: string
  multiplier: string
}

export interface CampaignDraft {
  durationHours: string
  planType: 'fixed_budget' | 'target_kpi'
  totalBudget: MoneyText
  optimize: 'unique_reach' | 'clicks' | 'conversions'
  strategy: 'uniform' | 'optimized'
  targetMetric: 'unique_reach' | 'clicks' | 'conversions'
  targetValue: string
  kpiCompletionPolicy: 'stop_at_kpi' | 'spend_budget'
  execution: ExecutionMode
  useHistory: boolean
}

/** How the campaign is run after the plan is approved. */
export type ExecutionMode = 'adaptive_max' | 'adaptive' | 'frozen'
export const EXECUTION_MODES: readonly ExecutionMode[] = ['adaptive_max', 'adaptive', 'frozen']

export interface LaunchDraft {
  simulation: SimulationDraft
  campaign: CampaignDraft
}

export interface ActiveRun {
  simulationId: string
  status: SimulationStatus
  completionReason?: 'kpi_reached' | 'budget_spent'
  currentHour: string
  endHourExclusive: string
  durationHours: number
  remainingHours: number
  timeZone: string
  currency: string
  engineVersion: string
  worldConfigDigest: string
  channelIds: ChannelID[]
  etag: string | null
}

export interface Observation {
  channelId: ChannelID
  hour: string
  requests: bigint
  impressions: bigint
  uniqueReach: bigint
  clicks: bigint
  conversions: bigint
  spend: MoneyText
  ecpm: MoneyText | null
}

export interface HourlyAggregate {
  requests: bigint
  impressions: bigint
  uniqueReach: bigint
  clicks: bigint
  conversions: bigint
  spend: MoneyText
  ecpm: MoneyText | null
}

export interface HourlyResult {
  simulationId: string
  stepId: string
  observedHour: string
  nextHour: string
  status: SimulationStatus
  remainingHours: number
  observations: Observation[]
  aggregate?: HourlyAggregate
}

export interface ChannelBudget {
  channelId: ChannelID
  budgetCap: MoneyText
}

export interface PendingStep {
  stepId: string
  expectedHour: string
  actions: readonly ChannelBudget[]
  etag: string | null
  attempt: number
}

export type ExecutionStatus = 'idle' | 'stepping' | 'running' | 'stopping' | 'stopped' | 'error'
