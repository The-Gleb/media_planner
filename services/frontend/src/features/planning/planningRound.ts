import type { FixedBudgetPlanRequest, MediaPlan, PendingPlanningRound } from '../../domain/planning'
import { activatePlan } from './activePlan'
function deepFreeze<T>(value:T):T { if(value && typeof value === 'object'){ Object.freeze(value); for(const child of Object.values(value as Record<string, unknown>)) deepFreeze(child) } return value }
function immutableRequest(request:FixedBudgetPlanRequest):FixedBudgetPlanRequest { return deepFreeze(structuredClone(request)) }
export function createPlanningRound(request:FixedBudgetPlanRequest,expectedPlanId:string|null=null):PendingPlanningRound { const snapshot=immutableRequest(request); return Object.freeze({requestId:snapshot.request_id,stateRevision:snapshot.current.state_revision,expectedPlanId,request:snapshot,attempt:1}) }
export function retryPlanningRound(round:PendingPlanningRound):PendingPlanningRound { return Object.freeze({...round,request:round.request,attempt:round.attempt+1}) }
export function acceptPlanningRound(round:PendingPlanningRound,plan:MediaPlan,channels:readonly string[]) { return activatePlan(plan,round.requestId,round.stateRevision,channels,round.expectedPlanId??undefined,round.request) }
