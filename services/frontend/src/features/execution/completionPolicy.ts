import type { CampaignFacts } from '../../domain/planning'
import type { ActiveRun, CampaignDraft, ChannelBudget } from '../../domain/types'
import { formatMoney, parseMoney } from '../../domain/numeric'

export function targetReached(campaign: CampaignDraft, facts: CampaignFacts): boolean {
  const metric = campaign.targetMetric === 'unique_reach' ? 'uniqueReach' : campaign.targetMetric
  return campaign.planType === 'target_kpi' && BigInt(facts[metric]) >= BigInt(campaign.targetValue)
}

/** Campaign completion is local: the simulator has no early-termination endpoint. */
export function applyCompletionPolicy(session: ActiveRun, campaign: CampaignDraft, facts: CampaignFacts): ActiveRun {
  if (campaign.planType !== 'target_kpi') return session
  const completionReason = campaign.kpiCompletionPolicy === 'stop_at_kpi' && targetReached(campaign, facts)
    ? 'kpi_reached'
    : parseMoney(facts.spent) >= parseMoney(campaign.totalBudget) ? 'budget_spent' : undefined
  return completionReason ? { ...session, status: 'finished', completionReason } : session
}

/** Offer at least the remaining hourly pace, including planner reserves, after the goal. */
export function remainingBudgetActions(actions: readonly ChannelBudget[], session: ActiveRun, campaign: CampaignDraft, facts: CampaignFacts) {
  if (campaign.kpiCompletionPolicy !== 'spend_budget' || !targetReached(campaign, facts) || session.remainingHours <= 0 || actions.length === 0) return actions
  const remaining = parseMoney(campaign.totalBudget) - parseMoney(facts.spent)
  if (remaining <= 0n) return actions.map(action => ({ ...action, budgetCap: '0.000000' }))
  const planned = actions.reduce((sum, action) => sum + parseMoney(action.budgetCap), 0n)
  const pace = (remaining + BigInt(session.remainingHours) - 1n) / BigInt(session.remainingHours)
  const hourlyBudget = planned > pace ? planned : pace
  const desired = hourlyBudget > remaining ? remaining : hourlyBudget
  let assigned = 0n
  return actions.map((action, index) => {
    const cap = index === actions.length - 1 ? desired - assigned
      : planned > 0n ? desired * parseMoney(action.budgetCap) / planned : desired / BigInt(actions.length)
    assigned += cap
    return { ...action, budgetCap: formatMoney(cap) }
  })
}
