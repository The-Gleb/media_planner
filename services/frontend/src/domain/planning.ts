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
export interface HourlyExpected { spend: MoneyText; impressions: string; uniqueReach: string; clicks: string; conversions: string }
export interface Allocation { channelId: ChannelID; hour: number; budgetCap: MoneyText; expected: HourlyExpected | null }
export interface TargetKPI { metric: KPI; value: string }
export interface ExpectedOutcome { spend: MoneyText; impressions: string; uniqueReach: string; clicks: string; conversions: string }
export interface MediaPlan {
  requestId: string; stateRevision: number; planId: string; feasible: true; type: PlanType
  strategy: Strategy; optimize: KPI; currency: string; budget: MoneyText; horizon: Horizon
  expected: ExpectedOutcome | null; allocations: Allocation[]; unallocatedBudget: MoneyText; requiredBudget: MoneyText | null; reason: null; target: TargetKPI | null
}
export interface InfeasibleTargetPlan {
  requestId: string; stateRevision: 0; planId: null; feasible: false; type: 'target_kpi'; strategy: 'optimized'; optimize: KPI
  currency: string; budget: null; horizon: Horizon; expected: ExpectedOutcome; allocations: []; unallocatedBudget: null
  requiredBudget: null; target: TargetKPI
  reason: { code: 'target_exceeds_capacity'; detail: string; maxAchievable: string; recommendedTarget: string }
}
export type PlanResult = MediaPlan | InfeasibleTargetPlan
export interface ActivePlan extends MediaPlan { index: ReadonlyMap<number, ReadonlyMap<ChannelID, MoneyText>> }
export interface FixedBudgetPlanRequest {
  request_id: string; type: 'fixed_budget'; strategy: Strategy; horizon: { from_hour: number; to_hour: number }
  channels: string[]
  simulation: { simulation_id: string; world_seed: string; campaign_seed: string; start_hour: string; time_zone: string; currency: string; world_config_digest: string }
  market: { status: 'unavailable' }
  current: { current_hour: number; state_revision: number; last_step_id: string | null; last_observed_at: string | null; spent: string; unique_reach: string; clicks: string; conversions: string; channels: Record<string, { spent: string; requests: string; impressions: string; unique_reach: string; clicks: string; conversions: string }> }
  budget: string; optimize: KPI; target: null
}
export interface TargetKPIPlanRequest {
  request_id: string; type: 'target_kpi'; strategy: 'optimized'; horizon: { from_hour: number; to_hour: number }
  channels: string[]; simulation: FixedBudgetPlanRequest['simulation']; market: { status: 'unavailable' }
  current: FixedBudgetPlanRequest['current']; budget: null; optimize: null; target: { metric: KPI; value: string }
}
export type PlanRequest = FixedBudgetPlanRequest | TargetKPIPlanRequest
export interface PlanRequestInput {
  simulation: SimulationDraft; durationHours: number; channels: ChannelID[]; currency: string
  worldConfigDigest: string; budget: MoneyText; optimize: KPI; strategy?: Strategy; facts: CampaignFacts; requestId?: string
}
export interface TargetPlanRequestInput extends Omit<PlanRequestInput, 'budget' | 'optimize' | 'strategy'> {
  targetMetric: KPI; targetValue: string
}
export interface PendingPlanningRound {
  readonly requestId: string; readonly stateRevision: number; readonly expectedPlanId: string | null
  readonly request: FixedBudgetPlanRequest; readonly attempt: number
  readonly targetPresentation: Pick<MediaPlan, 'type' | 'target' | 'expected' | 'requiredBudget'> | null
}
export interface CompletedRun {
  strategy: Strategy
  optimize: KPI
  planId: string
  facts: CampaignFacts
}
