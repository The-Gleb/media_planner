import type { ChannelID, MoneyText, SimulationDraft } from './types'

export type KPI = 'unique_reach' | 'clicks' | 'conversions'
export type PlanType = 'fixed_budget' | 'target_kpi'
export type Strategy = 'uniform' | 'optimized'

export interface FixedBudgetPlanningDraft { planType: 'fixed_budget'; totalBudget: MoneyText; optimize: KPI; strategy: Strategy }
export interface TargetKPIPlanningDraft { planType: 'target_kpi'; targetMetric: KPI; targetValue: string; strategy: Strategy }
export type PlanningDraft = FixedBudgetPlanningDraft | TargetKPIPlanningDraft

export interface ChannelFacts { spent: MoneyText; requests: string; impressions: string; uniqueReach: string; clicks: string; conversions: string }
export interface CampaignFacts {
  currentHour: number; stateRevision: number; lastStepId: string | null; lastObservedAt: string | null
  spent: MoneyText; uniqueReach: string; clicks: string; conversions: string
  channels: Record<ChannelID, ChannelFacts>
}
export interface Horizon { fromHour: number; toHour: number }
export interface Allocation { channelId: ChannelID; hour: number; budgetCap: MoneyText; expected: null }
export interface MediaPlan {
  requestId: string; stateRevision: number; planId: string; feasible: true; type: 'fixed_budget'
  strategy: Strategy; optimize: KPI; currency: string; budget: MoneyText; horizon: Horizon
  expected: null; allocations: Allocation[]; requiredBudget: null; reason: null
}
export interface ActivePlan extends MediaPlan { index: ReadonlyMap<number, ReadonlyMap<ChannelID, MoneyText>> }
export interface FixedBudgetPlanRequest {
  request_id: string; type: 'fixed_budget'; strategy: Strategy; horizon: { from_hour: number; to_hour: number }
  channels: string[]
  simulation: { simulation_id: string; world_seed: string; campaign_seed: string; start_hour: string; time_zone: string; currency: string; world_config_digest: string }
  market: { status: 'unavailable' }
  current: { current_hour: number; state_revision: number; last_step_id: string | null; last_observed_at: string | null; spent: string; unique_reach: string; clicks: string; conversions: string; channels: Record<string, { spent: string; requests: string; impressions: string; unique_reach: string; clicks: string; conversions: string }> }
  budget: string; optimize: KPI; target: null
}
export interface PlanRequestInput {
  simulation: SimulationDraft; durationHours: number; channels: ChannelID[]; currency: string
  worldConfigDigest: string; budget: MoneyText; optimize: KPI; strategy?: Strategy; facts: CampaignFacts; requestId?: string
}
export interface PendingPlanningRound {
  readonly requestId: string; readonly stateRevision: number; readonly expectedPlanId: string | null
  readonly request: FixedBudgetPlanRequest; readonly attempt: number
}
export interface CompletedRun {
  strategy: Strategy
  optimize: KPI
  planId: string
  facts: CampaignFacts
}
