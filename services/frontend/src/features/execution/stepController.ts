import type { ActivePlan } from '../../domain/planning'
import type { ActiveRun, PendingStep } from '../../domain/types'
import type { SimulatorClient } from '../../api/simulatorClient'
import { plannedActions } from './plannedActions'
export function createPendingStep(session:ActiveRun,plan:ActivePlan):PendingStep { const relativeHour=session.durationHours-session.remainingHours;return{stepId:crypto.randomUUID(),expectedHour:session.currentHour,actions:plannedActions(plan,relativeHour,session.channelIds),etag:session.etag,attempt:1} }
export function retryPendingStep(pending:PendingStep):PendingStep{return{...pending,attempt:pending.attempt+1}}
export async function submitPendingStep(client:SimulatorClient,session:ActiveRun,pending:PendingStep){return client.step(session.simulationId,{step_id:pending.stepId,actions:pending.actions.map(a=>({channel_id:a.channelId,budget_cap:a.budgetCap}))},pending.etag)}
